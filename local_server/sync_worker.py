"""Синхронізація локальних відміток переклички з хмарою.

Працює як фоновий потік локального сервера (запускається з main.py),
а також окремо: `python sync_worker.py`.
"""

import logging
import threading
import uuid

import httpx
from sqlalchemy.orm import Session

import config
import database
import models
from cloud import CloudClient, CloudError, NotConnected
from models import LocalSession, Mark, RosterStudent, get_state
from utils import iso_utc, utcnow

log = logging.getLogger("shelter.sync")

BATCH_SIZE = 100  # максимум подій у POST /sync/events


def init_db() -> None:
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    try:
        get_state(db)
    finally:
        db.close()


def build_event(mark: Mark, session: LocalSession, device_id: str) -> dict:
    return {
        "client_event_id": mark.client_event_id,
        "type": "rollcall_status",
        "device_id": device_id,
        "occurred_at": iso_utc(mark.occurred_at),
        "student_id": mark.student_id,
        "payload": {"session_id": session.effective_id, "status": mark.status},
    }


def refresh_class_data(db: Session, cloud: CloudClient) -> None:
    """Оновлює відкриту хмарну перекличку й кеш списку учнів."""
    state = cloud.state
    current = cloud.get_current_rollcall(state.class_id)
    session = current.get("session")
    state.cloud_session_id = (
        str(session["id"]) if session and not session.get("closed_at") else None
    )
    roster = cloud.fetch_roster(state.class_id, current)
    if roster:  # порожній/невідомий список не стирає кеш
        db.query(RosterStudent).delete()
        for s in roster:
            db.add(RosterStudent(**s))
        state.roster_updated_at = utcnow()
    db.commit()


def register_sessions(db: Session, cloud: CloudClient) -> None:
    """Реєструє в хмарі локальні переклички; при 409 бере id уже відкритої сесії."""
    pending = db.query(LocalSession).filter(LocalSession.registered.is_(False)).all()
    for s in pending:
        try:
            cloud_id = cloud.register_session(s.class_id, s.id)
        except CloudError as e:
            log.warning("Не вдалося зареєструвати перекличку %s: HTTP %s", s.id, e.status)
            continue
        s.registered = True
        s.cloud_id = cloud_id if cloud_id != s.id else None
        db.commit()
        if s.cloud_id:
            log.info("Перекличка %s вже відкрита в хмарі як %s", s.id, s.cloud_id)


def apply_results(db: Session, results: list[dict]) -> dict[str, int]:
    counts = {"accepted": 0, "duplicate": 0, "rejected": 0}
    for res in results:
        mark = db.get(Mark, str(uuid.UUID(str(res["client_event_id"]))))
        if mark is None:
            continue
        status = res.get("status")
        if status in ("accepted", "duplicate"):
            mark.sync_state = "synced"
            mark.reject_reason = None
        elif status == "rejected":
            mark.sync_state = "rejected"
            mark.reject_reason = res.get("reason") or "unknown"
        else:
            continue
        counts[status] += 1
    db.commit()
    return counts


def push_marks(db: Session, cloud: CloudClient) -> dict[str, int]:
    """Відправляє відмітки зареєстрованих перекличок пачками по ≤100."""
    rows = (
        db.query(Mark, LocalSession)
        .join(LocalSession, Mark.session_id == LocalSession.id)
        .filter(Mark.sync_state == "pending", LocalSession.registered.is_(True))
        .order_by(Mark.occurred_at)
        .all()
    )
    total = {"accepted": 0, "duplicate": 0, "rejected": 0}
    device_id = cloud.state.device_id
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        results = cloud.send_events([build_event(m, s, device_id) for m, s in batch])
        for k, v in apply_results(db, results).items():
            total[k] += v
    return total


def run_cycle(db: Session, transport: httpx.BaseTransport | None = None) -> str:
    """Один цикл синхронізації. Ніколи не кидає винятків; повертає короткий підсумок."""
    state = get_state(db)
    if not state.connected:
        return "not_connected"
    error = None
    try:
        with CloudClient(db, state, transport=transport) as cloud:
            if state.class_id:
                refresh_class_data(db, cloud)
            register_sessions(db, cloud)
            counts = push_marks(db, cloud)
        if any(counts.values()):
            log.info(
                "Синхронізовано: прийнято %(accepted)s, дублів %(duplicate)s, відхилено %(rejected)s",
                counts,
            )
    except NotConnected:
        error = "Потрібно знову підключитися до ShelterED"
    except httpx.TransportError as e:
        error = "Немає зв'язку з хмарою"
        log.info("Немає зв'язку з хмарою (%s)", type(e).__name__)
    except CloudError as e:
        error = f"Хмара відповіла помилкою HTTP {e.status}"
        log.warning(error)
    except Exception:
        error = "Внутрішня помилка синхронізації"
        log.exception(error)

    db.rollback()
    state = get_state(db)
    state.last_sync_error = error
    if error is None:
        state.last_sync_at = utcnow()
    db.commit()
    return error or "ok"


# ---------- фоновий потік ----------

_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


def wake() -> None:
    """Запустити цикл синхронізації негайно (напр. після підключення вчителя)."""
    _wake.set()


def sync_loop(interval: float = config.SYNC_INTERVAL_S) -> None:
    log.info("Фонова синхронізація запущена (кожні %s с, хмара %s)", interval, config.CLOUD_API_URL)
    while not _stop.is_set():
        db = database.SessionLocal()
        try:
            run_cycle(db)
        except Exception:
            log.exception("Помилка циклу синхронізації")
        finally:
            db.close()
        _wake.wait(interval)
        _wake.clear()


def start_background() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=sync_loop, name="sync-worker", daemon=True)
    _thread.start()


def stop_background() -> None:
    _stop.set()
    _wake.set()
    if _thread:
        _thread.join(timeout=config.HTTP_TIMEOUT_S + 5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    init_db()
    try:
        sync_loop()
    except KeyboardInterrupt:
        pass
