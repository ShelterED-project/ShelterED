from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.errors import AppError
from app.main import create_app

app = create_app()


@app.get("/_test/app-error")
async def raise_app_error():
    raise AppError("LESSON_NOT_FOUND", "Lesson not found", status_code=404, details={"id": "x"})


@app.get("/_test/http-error")
async def raise_http_error():
    raise HTTPException(status_code=403, detail="Forbidden for this role")


@app.get("/_test/validation")
async def needs_int(limit: int):
    return {"limit": limit}


@app.get("/_test/crash")
async def crash():
    raise RuntimeError("boom")


client = TestClient(app, raise_server_exceptions=False)


def test_app_error():
    response = client.get("/_test/app-error")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "LESSON_NOT_FOUND", "message": "Lesson not found", "details": {"id": "x"}}
    }


def test_http_error():
    response = client.get("/_test/http-error")
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "Forbidden for this role",
        "details": None,
    }


def test_unknown_route():
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_validation_error_hides_input():
    response = client.get("/_test/validation", params={"limit": "secret-value"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["loc"] == ["query", "limit"]
    assert "secret-value" not in response.text


def test_unhandled_error():
    response = client.get("/_test/crash")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "boom" not in response.text
