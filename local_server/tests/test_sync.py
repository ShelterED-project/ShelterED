import json
import re
import uuid
from datetime import timedelta

import httpx
from conftest import CLASS_ID

import sync_worker
from models import LocalSession, Mark, RosterStudent, get_state
from utils import utcnow, uuid7

STUDENT = "0192f0a0-0000-7000-8000-0000000000cc"


def add_session(db, registered=True, sid=None):
    s = LocalSession(
        id=sid or str(uuid7()), class_id=CLASS_ID, started_at=utcnow(), registered=registered
    )
    db.add(s)
    db.commit()
    return s


def add_mark(db, session, status="in_shelter", student=STUDENT, offset_s=0):
    m = Mark(
        client_event_id=str(uuid7()),
        session_id=session.id,
        student_id=student,
        status=status,
        occurred_at=utcnow() + timedelta(seconds=offset_s),
    )
    db.add(m)
    db.commit()
    return m


def results_response(statuses):
    """Відповідь /sync/events зі статусами за порядком подій у пакеті."""

    def handler(request):
        events = json.loads(request.content)["events"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "client_event_id": e["client_event_id"],
                        "status": st,
                        "reason": "session_closed" if st == "rejected" else None,
                    }
                    for e, st in zip(events, statuses)
                ],
                "server_time": "2026-11-16T10:00:00Z",
            },
        )

    return handler


# ---------- UUID v7 ----------


def test_uuid7_format_and_order():
    a = uuid7()
    assert a.version == 7
    assert a.variant == uuid.RFC_4122
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", str(a)
    )
    ms = a.int >> 80
    assert abs(ms - int(utcnow().timestamp() * 1000)) < 5000
    assert len({uuid7() for _ in range(1000)}) == 1000


# ---------- формат подій і результати ----------


def test_event_envelope_matches_contract(db, connected, cloud):
    s = add_session(db)
    m = add_mark(db, s, status="safe")
    assert sync_worker.run_cycle(db, cloud.transport()) == "ok"

    (batch,) = cloud.sent_events()
    assert batch["sent_at"].endswith("Z")
    (event,) = batch["events"]
    assert event == {
        "client_event_id": m.client_event_id,
        "type": "rollcall_status",
        "device_id": connected.device_id,
        "occurred_at": event["occurred_at"],
        "student_id": STUDENT,
        "payload": {"session_id": s.id, "status": "safe"},
    }
    assert event["occurred_at"].endswith("Z")
    db.refresh(m)
    assert m.sync_state == "synced"


def test_accepted_duplicate_rejected(db, connected, cloud):
    s = add_session(db)
    marks = [add_mark(db, s, offset_s=i) for i in range(3)]
    cloud.routes[("POST", "/sync/events")] = results_response(["accepted", "duplicate", "rejected"])

    assert sync_worker.run_cycle(db, cloud.transport()) == "ok"
    for m in marks:
        db.refresh(m)
    assert [m.sync_state for m in marks] == ["synced", "synced", "rejected"]
    assert marks[2].reject_reason == "session_closed"

    # повторний цикл: нічого не відправляємо (відхилене не повторюємо)
    cloud.requests.clear()
    sync_worker.run_cycle(db, cloud.transport())
    assert cloud.sent_events() == []


def test_server_error_keeps_marks_pending(db, connected, cloud):
    s = add_session(db)
    m = add_mark(db, s)
    for status in (500, 501, 429, 422):
        cloud.routes[("POST", "/sync/events")] = lambda r, st=status: httpx.Response(st, json={})
        result = sync_worker.run_cycle(db, cloud.transport())
        assert str(status) in result
        db.refresh(m)
        assert m.sync_state == "pending"
    assert get_state(db).last_sync_error


def test_network_error_keeps_marks_pending(db, connected):
    s = add_session(db)
    m = add_mark(db, s)

    def boom(request):
        raise httpx.ConnectError("no internet", request=request)

    assert sync_worker.run_cycle(db, httpx.MockTransport(boom)) == "Немає зв'язку з хмарою"
    db.refresh(m)
    assert m.sync_state == "pending"


def test_batches_of_at_most_100(db, connected, cloud):
    s = add_session(db)
    for i in range(250):
        add_mark(db, s, student=str(uuid7()), offset_s=i)
    sync_worker.run_cycle(db, cloud.transport())
    sizes = [len(b["events"]) for b in cloud.sent_events()]
    assert sizes == [100, 100, 50]
    assert db.query(Mark).filter(Mark.sync_state == "pending").count() == 0


def test_not_connected_does_nothing(db, cloud):
    s = add_session(db)
    add_mark(db, s)
    assert sync_worker.run_cycle(db, cloud.transport()) == "not_connected"
    assert cloud.requests == []


# ---------- реєстрація переклички ----------


def test_register_session_then_send(db, connected, cloud):
    s = add_session(db, registered=False)
    add_mark(db, s)
    sync_worker.run_cycle(db, cloud.transport())
    db.refresh(s)
    assert s.registered and s.cloud_id is None
    (batch,) = cloud.sent_events()
    assert batch["events"][0]["payload"]["session_id"] == s.id


def test_409_remaps_session(db, connected, cloud):
    other = "0192f0a0-0000-7000-8000-000000000801"
    cloud.routes[("POST", f"/classes/{CLASS_ID}/rollcall")] = lambda r: httpx.Response(
        409,
        json={
            "error": {
                "code": "ROLLCALL_ALREADY_OPEN",
                "message": "...",
                "details": {"session_id": other},
            }
        },
    )
    s = add_session(db, registered=False)
    add_mark(db, s)
    sync_worker.run_cycle(db, cloud.transport())
    db.refresh(s)
    assert s.registered and s.cloud_id == other
    (batch,) = cloud.sent_events()
    assert batch["events"][0]["payload"]["session_id"] == other


def test_unregistered_session_marks_wait(db, connected, cloud):
    cloud.routes[("POST", f"/classes/{CLASS_ID}/rollcall")] = lambda r: httpx.Response(503)
    s = add_session(db, registered=False)
    m = add_mark(db, s)
    sync_worker.run_cycle(db, cloud.transport())
    db.refresh(s)
    db.refresh(m)
    assert not s.registered
    assert m.sync_state == "pending"
    assert cloud.sent_events() == []


# ---------- токени ----------


def test_refresh_on_401_and_rotation(db, connected, cloud):
    cloud.valid_access = {"expired-on-server"}  # сервер уже не приймає access-1
    s = add_session(db)
    m = add_mark(db, s)
    assert sync_worker.run_cycle(db, cloud.transport()) == "ok"
    assert cloud.refresh_calls == 1
    st = get_state(db)
    assert st.access_token == "access-2"
    assert st.refresh_token == "refresh-2"  # зберегли новий refresh
    db.refresh(m)
    assert m.sync_state == "synced"


def test_refresh_before_expiry(db, connected, cloud):
    connected.access_expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    sync_worker.run_cycle(db, cloud.transport())
    assert cloud.refresh_calls == 1
    assert get_state(db).refresh_token == "refresh-2"


def test_rejected_refresh_disconnects(db, connected, cloud):
    cloud.valid_access = set()
    cloud.routes[("POST", "/auth/token")] = lambda r: httpx.Response(
        401, json={"error": {"code": "INVALID_GRANT"}}
    )
    s = add_session(db)
    m = add_mark(db, s)
    result = sync_worker.run_cycle(db, cloud.transport())
    assert "підключитися" in result
    st = get_state(db)
    assert st.refresh_token is None and not st.connected
    db.refresh(m)
    assert m.sync_state == "pending"  # відмітки не губимо


# ---------- список учнів і хмарна сесія ----------


def test_roster_from_open_session(db, connected, cloud):
    cloud_session = "0192f0a0-0000-7000-8000-000000000801"
    cloud.routes[("GET", f"/classes/{CLASS_ID}/rollcall/current")] = lambda r: httpx.Response(
        200,
        json={
            "class_id": CLASS_ID,
            "session": {
                "id": cloud_session,
                "closed_at": None,
                "students": [
                    {
                        "student_id": STUDENT,
                        "display_name": "Іван",
                        "last_name": "Петренко",
                        "status": "no_response",
                        "occurred_at": None,
                        "received_at": None,
                    }
                ],
            },
        },
    )
    sync_worker.run_cycle(db, cloud.transport())
    assert get_state(db).cloud_session_id == cloud_session
    (st,) = db.query(RosterStudent).all()
    assert (st.student_id, st.full_name) == (STUDENT, "Іван Петренко")


def test_roster_from_students_endpoint_and_kept_when_unknown(db, connected, cloud):
    cloud.routes[("GET", f"/classes/{CLASS_ID}/students")] = lambda r: httpx.Response(
        200, json=[{"student_id": STUDENT, "display_name": "Іван", "last_name": None}]
    )
    sync_worker.run_cycle(db, cloud.transport())
    assert db.query(RosterStudent).count() == 1

    # ендпоінта немає (старий бекенд) і немає сесії — кеш лишається
    del cloud.routes[("GET", f"/classes/{CLASS_ID}/students")]
    sync_worker.run_cycle(db, cloud.transport())
    assert db.query(RosterStudent).count() == 1
