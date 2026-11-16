from fastapi.testclient import TestClient

import main
from models import LocalSession, get_state

CLOUD_SESSION = "0192f0a0-0000-7000-8000-000000000901"


def client_for(db) -> TestClient:
    main.app.dependency_overrides[main.get_db] = lambda: db
    # Без `with`: lifespan (фонова синхронізація) у тестах не запускаємо.
    return TestClient(main.app)


def test_restart_after_finish_creates_new_session_even_if_cloud_id_is_stale(db, connected):
    get_state(db).cloud_session_id = CLOUD_SESSION
    db.commit()
    client = client_for(db)
    try:
        client.post("/teacher/start")
        first = db.query(LocalSession).one()
        assert first.id == CLOUD_SESSION and first.registered  # продовжуємо хмарну перекличку

        client.post("/teacher/finish")
        # Мережі немає: id хмарної переклички в стані лишився (міг застаріти).
        client.post("/teacher/start")
        sessions = db.query(LocalSession).order_by(LocalSession.started_at).all()
        assert len(sessions) == 2
        old, new = sessions
        assert old.ended_at is not None  # завершену не відкриваємо знову
        assert new.id != CLOUD_SESSION and not new.registered and new.ended_at is None
    finally:
        main.app.dependency_overrides.clear()
