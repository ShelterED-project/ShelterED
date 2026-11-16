"""Клієнт хмарного API ShelterED (від імені вчителя).

Токени лежать у таблиці local_state. Пароль ніде не зберігається й не логується.
"""

import base64
import hashlib
import json
import logging
import secrets
from datetime import timedelta

import httpx
from sqlalchemy.orm import Session

import config
from models import State
from utils import iso_utc, utcnow

log = logging.getLogger("shelter.cloud")


class NotConnected(Exception):
    """Немає дійсних токенів: вчитель має підключитися знову."""


class LoginFailed(Exception):
    """Повідомлення для вчителя (українською)."""


class CloudError(Exception):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)  # 64 символи
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _student(raw: dict) -> dict:
    return {
        "student_id": str(raw.get("student_id") or raw["id"]),
        "display_name": raw["display_name"],
        "last_name": raw.get("last_name"),
    }


class CloudClient:
    def __init__(
        self,
        db: Session,
        state: State,
        base_url: str = config.CLOUD_API_URL,
        transport: httpx.BaseTransport | None = None,
    ):
        self.db = db
        self.state = state
        self.http = httpx.Client(
            base_url=base_url, timeout=config.HTTP_TIMEOUT_S, transport=transport
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.http.close()

    # ---------- токени ----------

    def _save_tokens(self, data: dict) -> None:
        st = self.state
        st.access_token = data["access_token"]
        st.refresh_token = data["refresh_token"]  # refresh ротується: завжди беремо новий
        st.access_expires_at = utcnow() + timedelta(seconds=int(data.get("expires_in", 300)))
        self.db.commit()

    def clear_tokens(self) -> None:
        st = self.state
        st.access_token = st.refresh_token = st.access_expires_at = None
        self.db.commit()

    def login(self, email: str, password: str) -> None:
        """OAuth 2.0 Authorization Code + PKCE (S256); потім перевірка ролі й список класів."""
        verifier, challenge = pkce_pair()
        r = self.http.post(
            "/auth/authorize",
            json={
                "email": email,
                "password": password,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "client_id": config.CLIENT_ID,
            },
        )
        if r.status_code == 429:
            raise LoginFailed("Забагато спроб входу. Спробуйте за хвилину.")
        if r.status_code in (400, 401, 403, 422):
            raise LoginFailed("Невірний email або пароль.")
        if r.status_code != 200:
            raise CloudError(r.status_code, r.text[:500])

        r = self.http.post(
            "/auth/token",
            json={
                "grant_type": "authorization_code",
                "code": r.json()["code"],
                "code_verifier": verifier,
                "client_id": config.CLIENT_ID,
            },
        )
        if r.status_code != 200:
            raise CloudError(r.status_code, r.text[:500])
        tokens = r.json()

        me = self.http.get(
            "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        if me.status_code != 200:
            raise CloudError(me.status_code, me.text[:500])
        me = me.json()
        if me.get("role") != "teacher":
            raise LoginFailed("Підключити локальний сервер може лише вчитель.")

        self.state.teacher_name = (
            f"{me.get('display_name', '')} {me.get('last_name') or ''}".strip()
        )
        self._save_tokens(tokens)

        classes = [{"id": str(c["id"]), "name": c["name"]} for c in self.get_classes()]
        self.state.classes_json = json.dumps(classes, ensure_ascii=False)
        if self.state.class_id not in {c["id"] for c in classes}:
            self.state.class_id = self.state.class_name = None
        if len(classes) == 1:
            self.state.class_id = classes[0]["id"]
            self.state.class_name = classes[0]["name"]
        self.db.commit()

    def refresh(self) -> None:
        if not self.state.refresh_token:
            raise NotConnected()
        r = self.http.post(
            "/auth/token",
            json={"grant_type": "refresh_token", "refresh_token": self.state.refresh_token},
        )
        if r.status_code in (400, 401, 403):
            log.warning("Refresh-токен відхилено (%s): потрібно підключитися знову", r.status_code)
            self.clear_tokens()
            raise NotConnected()
        if r.status_code != 200:
            raise CloudError(r.status_code, r.text[:500])
        self._save_tokens(r.json())

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Запит із Bearer-токеном; на 401 один раз оновлюємо токен і повторюємо."""
        st = self.state
        if not st.refresh_token:
            raise NotConnected()
        if (
            not st.access_token
            or st.access_expires_at is None
            or st.access_expires_at - utcnow() < timedelta(seconds=30)
        ):
            self.refresh()

        def send() -> httpx.Response:
            headers = {"Authorization": f"Bearer {self.state.access_token}"}
            return self.http.request(method, path, headers=headers, **kwargs)

        r = send()
        if r.status_code == 401:
            self.refresh()
            r = send()
            if r.status_code == 401:
                raise CloudError(401, r.text[:500])
        return r

    # ---------- дані класу ----------

    def get_classes(self) -> list[dict]:
        r = self.request("GET", "/classes")
        if r.status_code != 200:
            raise CloudError(r.status_code, r.text[:500])
        return r.json()

    def get_current_rollcall(self, class_id: str) -> dict:
        r = self.request("GET", f"/classes/{class_id}/rollcall/current")
        if r.status_code != 200:
            raise CloudError(r.status_code, r.text[:500])
        return r.json()

    def fetch_roster(self, class_id: str, current: dict | None = None) -> list[dict] | None:
        """Список учнів класу: [{student_id, display_name, last_name}] або None, якщо невідомо.

        GET /classes/{id}/students (вчитель класу); якщо ендпоінта немає (старий бекенд) —
        учні з відкритої переклички GET /classes/{id}/rollcall/current.
        """
        r = self.request("GET", f"/classes/{class_id}/students")
        if r.status_code == 200 and isinstance(r.json(), list):
            return [_student(s) for s in r.json()]
        if r.status_code != 404:
            raise CloudError(r.status_code, r.text[:500])

        if current is None:
            current = self.get_current_rollcall(class_id)
        session = current.get("session")
        if session and isinstance(session.get("students"), list):
            return [_student(s) for s in session["students"]]
        return None

    def register_session(self, class_id: str, session_id: str) -> str:
        """Реєструє перекличку з локальним id. Повертає id сесії в хмарі (інший при 409)."""
        r = self.request("POST", f"/classes/{class_id}/rollcall", json={"id": session_id})
        if r.status_code in (200, 201):
            return session_id
        if r.status_code == 409:
            error = r.json().get("error") or {}
            other = (error.get("details") or {}).get("session_id")
            if error.get("code") == "ROLLCALL_ALREADY_OPEN" and other:
                return str(other)
        raise CloudError(r.status_code, r.text[:500])

    def send_events(self, events: list[dict]) -> list[dict]:
        r = self.request(
            "POST", "/sync/events", json={"sent_at": iso_utc(utcnow()), "events": events}
        )
        if r.status_code == 200:
            return r.json()["results"]
        if r.status_code == 422:
            log.error("422 від /sync/events (помилка контракту): %s", r.text[:1000])
        raise CloudError(r.status_code, r.text[:500])
