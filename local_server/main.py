import json
import logging
import sys
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import httpx
import qrcode
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import config
import database
import sync_worker
from cloud import CloudClient, CloudError, LoginFailed
from models import STATUSES, LocalSession, Mark, RosterStudent, active_session, get_state
from utils import to_kyiv, utcnow, uuid7

log = logging.getLogger("shelter.web")

# У .exe (PyInstaller) шаблони лежать у sys._MEIPASS, база — поруч із .exe
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_worker.init_db()
    sync_worker.start_background()
    yield
    sync_worker.stop_background()


app = FastAPI(title="ShelterED Local Server", lifespan=lifespan)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["kyiv"] = to_kyiv

STATUS_LABELS = {"in_shelter": "В укритті", "safe": "В безпеці вдома"}
SYNC_LABELS = {"synced": "Синхронізовано", "pending": "Очікує", "rejected": "Відхилено"}
STUDENT_COOKIE = "student_id"


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def redirect(url: str, msg: str | None = None) -> RedirectResponse:
    if msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    return RedirectResponse(url=url, status_code=303)


def latest_marks(db: Session, session_id: str) -> dict[str, Mark]:
    """Остання відмітка кожного учня в перекличці."""
    marks = (
        db.query(Mark)
        .filter(Mark.session_id == session_id)
        .order_by(Mark.occurred_at, Mark.client_event_id)
        .all()
    )
    return {m.student_id: m for m in marks}


def roster_list(db: Session) -> list[RosterStudent]:
    return (
        db.query(RosterStudent).order_by(RosterStudent.last_name, RosterStudent.display_name).all()
    )


# ---------- учень ----------


@app.get("/", response_class=HTMLResponse)
def student_page(request: Request, student: str | None = None, db: Session = Depends(get_db)):
    roster = roster_list(db)
    session = active_session(db)
    student_id = student or request.cookies.get(STUDENT_COOKIE)
    me = db.get(RosterStudent, student_id) if student_id else None
    mark = latest_marks(db, session.id).get(me.student_id) if (me and session) else None
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "roster": roster,
            "session": session,
            "me": me,
            "mark": mark,
            "status_labels": STATUS_LABELS,
        },
    )


@app.post("/mark")
def mark_status(
    student_id: str = Form(...), status: str = Form(...), db: Session = Depends(get_db)
):
    session = active_session(db)
    if status not in STATUSES or db.get(RosterStudent, student_id) is None or session is None:
        return redirect("/")
    db.add(
        Mark(
            client_event_id=str(uuid7()),
            session_id=session.id,
            student_id=student_id,
            status=status,
            occurred_at=utcnow(),
        )
    )
    db.commit()
    response = redirect(f"/?student={quote(student_id)}")
    response.set_cookie(STUDENT_COOKIE, student_id, max_age=60 * 60 * 24 * 180, samesite="lax")
    return response


@app.post("/forget-me")
def forget_me():
    response = redirect("/")
    response.delete_cookie(STUDENT_COOKIE)
    return response


# ---------- вчитель ----------


@app.get("/teacher", response_class=HTMLResponse)
def teacher_dashboard(request: Request, msg: str | None = None, db: Session = Depends(get_db)):
    state = get_state(db)
    session = active_session(db) or (
        db.query(LocalSession).order_by(LocalSession.started_at.desc()).first()
    )
    roster = roster_list(db)
    rows = []
    if session:
        marks = latest_marks(db, session.id)
        known = set()
        for s in roster:
            known.add(s.student_id)
            rows.append({"name": s.full_name, "mark": marks.get(s.student_id)})
        for sid, m in marks.items():
            if sid not in known:
                rows.append({"name": "Учень не зі списку", "mark": m})
    counts = {
        k: db.query(Mark).filter(Mark.sync_state == k).count() for k in ("pending", "rejected")
    }
    return templates.TemplateResponse(
        request=request,
        name="teacher.html",
        context={
            "state": state,
            "classes": json.loads(state.classes_json or "[]"),
            "session": session,
            "rows": rows,
            "roster_size": len(roster),
            "counts": counts,
            "msg": msg,
            "student_url": config.STUDENT_URL,
            "cloud_url": config.CLOUD_API_URL,
            "status_labels": STATUS_LABELS,
            "sync_labels": SYNC_LABELS,
        },
    )


@app.post("/teacher/connect")
def teacher_connect(
    email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)
):
    state = get_state(db)
    old_class = state.class_id
    try:
        with CloudClient(db, state) as cloud:
            cloud.login(email.strip(), password)
    except LoginFailed as e:
        return redirect("/teacher", str(e))
    except httpx.TransportError:
        return redirect(
            "/teacher", "Немає зв'язку з хмарою. Підключіться до інтернету й спробуйте ще раз."
        )
    except CloudError as e:
        log.warning("Вхід вчителя: хмара відповіла HTTP %s", e.status)
        return redirect("/teacher", f"Хмара відповіла помилкою HTTP {e.status}.")
    if state.class_id != old_class:
        _reset_class_cache(db)
    sync_worker.wake()
    return redirect("/teacher", "Підключено до ShelterED.")


def _reset_class_cache(db: Session) -> None:
    db.query(RosterStudent).delete()
    state = get_state(db)
    state.cloud_session_id = None
    state.roster_updated_at = None
    db.commit()


@app.post("/teacher/class")
def teacher_choose_class(class_id: str = Form(...), db: Session = Depends(get_db)):
    state = get_state(db)
    classes = {c["id"]: c["name"] for c in json.loads(state.classes_json or "[]")}
    if class_id not in classes:
        return redirect("/teacher")
    if active_session(db) and class_id != state.class_id:
        return redirect("/teacher", "Спершу завершіть поточну перекличку.")
    if class_id != state.class_id:
        state.class_id, state.class_name = class_id, classes[class_id]
        db.commit()
        _reset_class_cache(db)
    sync_worker.wake()
    return redirect("/teacher")


@app.post("/teacher/disconnect")
def teacher_disconnect(db: Session = Depends(get_db)):
    state = get_state(db)
    state.access_token = state.refresh_token = state.access_expires_at = None
    db.commit()
    return redirect("/teacher", "Відключено від ShelterED. Несинхронізовані відмітки збережено.")


@app.post("/teacher/start")
def teacher_start(db: Session = Depends(get_db)):
    state = get_state(db)
    if not state.class_id:
        return redirect("/teacher", "Спершу підключіться до ShelterED і оберіть клас.")
    if active_session(db) is None:
        # Якщо в хмарі відкрита перекличка, яку тут ще не завершували, — продовжуємо її.
        # Завершену локально не відкриваємо знову: id з хмари міг застаріти (її могли
        # закрити, поки не було мережі). Нова локальна сесія при реєстрації отримає 409,
        # якщо в хмарі відкрита інша, і відмітки перейдуть до неї.
        known_cloud = state.cloud_session_id
        if known_cloud and db.get(LocalSession, known_cloud) is not None:
            known_cloud = None
        db.add(
            LocalSession(
                id=known_cloud or str(uuid7()),
                class_id=state.class_id,
                started_at=utcnow(),
                registered=bool(known_cloud),
            )
        )
        db.commit()
        sync_worker.wake()
    return redirect("/teacher")


@app.post("/teacher/finish")
def teacher_finish(db: Session = Depends(get_db)):
    session = active_session(db)
    if session:
        session.ended_at = utcnow()
        db.commit()
    return redirect("/teacher")


@app.post("/teacher/sync")
def teacher_sync_now():
    sync_worker.wake()
    return redirect("/teacher", "Синхронізацію запущено.")


# ---------- службове ----------


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Локальний сервер працює"}


@app.get("/qr")
def generate_qr():
    # QR з адресою сторінки учня у Wi-Fi мережі вчителя
    img = qrcode.make(config.STUDENT_URL)
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")
