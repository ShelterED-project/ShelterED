"""Тести /ai/v1/test-analysis. Запуск з папки ai-service: pytest -q

LLM не викликається: або MOCK-режим, або підмінена функція complete.
"""

import copy
import json
import os
import re
import sys
from pathlib import Path

os.environ.update(AI_KEY="test", LLM_BASE_URL="http://llm.invalid", MODELS="m", INTERNAL_KEY="k")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.llm as llm  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

EXAMPLE = Path(__file__).resolve().parents[2] / "contracts" / "examples" / "test_analysis.json"
H = {"X-Internal-Key": "k"}


@pytest.fixture
def body():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_llm(monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM", True)


@pytest.fixture
def fake_llm(monkeypatch):
    """Підмінена модель: повертає валідний JSON і запам'ятовує всі промпти."""
    monkeypatch.setattr(settings, "MOCK_LLM", False)
    prompts = []

    def fake(system, user, **kw):
        prompts.append(system + "\n" + user)
        if "ключі рівно: q" in system:
            labels = re.search(r"ключі рівно: ([q0-9, ]+)\.", system).group(1).split(", ")
            skill = {"q1": "Додавання дробів", "q6": "Додавання дробів"}
            return json.dumps(
                {
                    lb: {"skill": skill.get(lb, f"Вміння {lb}"), "student_tip": f"tip {lb}", "parent_tip": f"ptip {lb}"}
                    for lb in labels
                },
                ensure_ascii=False,
            )
        ms = re.findall(r"^(m\d+): питання (\d+)", user, re.M)
        same = {"1", "5", "6"}  # одна причина — однаковий title
        return json.dumps(
            {
                "overview": "Висновок для вчителя.",
                "recommendations": ["Дія 1", "Дія 2"],
                "misconceptions": {
                    m: {
                        "title": "Додають знаменники" if p in same else f"Помилка {p}",
                        "teacher": "t",
                        "student_tip": "s",
                    }
                    for m, p in ms
                },
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(llm, "complete", fake)
    return prompts


def post(client, body, headers=H):
    return client.post("/ai/v1/test-analysis", json=body, headers=headers)


# ---------------------------------------------------------------- підрахунки


def test_stats_without_llm(client, body, mock_llm):
    r = post(client, body)
    assert r.status_code == 200
    d = r.json()
    cs = d["class_summary"]
    assert cs["students_total"] == 24
    assert cs["average_score_pct"] == 65.1
    assert cs["passed_count"] == 15
    assert len(cs["needs_support_ids"]) == 9
    assert cs["overview"] and cs["recommendations"]
    assert d["llm_used"] is False
    q1 = next(q for q in d["questions"] if q["question_id"] == "q1")
    assert q1["correct_pct"] == 50.0 and q1["status"] == "attention"
    assert q1["wrong_answers"][0] == {
        "option_ids": ["a"], "option_text": "3/10", "count": 12, "student_ids": q1["wrong_answers"][0]["student_ids"],
    }
    # Без LLM не пишемо «Добре виходить: Питання 1», а показуємо саме питання
    for s in d["students"]:
        assert "Добре виходить" not in s["feedback"]["student"]
    s10 = next(s for s in d["students"] if s["student_id"] == "stu_10")["feedback"]["student"]
    assert "Питання 1: «1/5 + 2/5 = ?»" in s10


def test_scoring_matches_backend(client, mock_llm):
    """Зараховано, лише якщо множина обраних == ключ; частково чи порожньо — ні."""
    body = {
        "grade": 5,
        "questions": [
            {"id": "a", "prompt": "?", "options": [{"id": "x", "text": "1"}, {"id": "y", "text": "2"}], "answer_key": ["x"], "points": 2},
            {"id": "b", "prompt": "?", "kind": "multiple",
             "options": [{"id": "x", "text": "1"}, {"id": "y", "text": "2"}, {"id": "z", "text": "3"}], "answer_key": ["x", "z"]},
        ],
        "students": [
            {"student_id": "s1", "answers": {"a": ["x"], "b": ["z", "x"]}},  # 100
            {"student_id": "s2", "answers": {"a": ["x"], "b": ["x"]}},       # частково → 66.7
            {"student_id": "s3", "answers": {"b": ["x", "z"]}},              # пропуск a → 33.3
        ],
    }
    d = post(client, body).json()
    scores = {s["student_id"]: s["score_pct"] for s in d["students"]}
    assert scores == {"s1": 100.0, "s2": 66.7, "s3": 33.3}
    statuses = {s["student_id"]: s["status"] for s in d["students"]}
    assert statuses == {"s1": "strong", "s2": "ok", "s3": "needs_support"}


# ---------------------------------------------------------------- LLM


def test_llm_never_sees_student_ids(client, body, fake_llm):
    r = post(client, body)
    assert r.status_code == 200
    assert r.json()["llm_used"] is True
    assert fake_llm, "LLM мала викликатися"
    for p in fake_llm:
        assert "stu_" not in p


def test_same_cause_misconceptions_are_merged(client, body, fake_llm):
    d = post(client, body).json()
    merged = [m for m in d["misconceptions"] if m["title"] == "Додають знаменники"]
    assert len(merged) == 1
    m = merged[0]
    assert m["question_ids"] == ["q1", "q5", "q6"]
    assert len(m["student_ids"]) == 12 and m["share_pct"] == 50.0
    assert {e["question_id"] for e in m["evidence"]} == {"q1", "q5", "q6"}
    # Учень посилається на об'єднаний id, а вміння з однаковою назвою агреговані
    assert any(m["id"] in s["misconception_ids"] for s in d["students"])
    add = next(sk for sk in d["skills"] if sk["skill"] == "Додавання дробів")
    assert add["question_ids"] == ["q1", "q6"]


def test_llm_down_still_returns_stats(client, body, monkeypatch):
    monkeypatch.setattr(settings, "MOCK_LLM", False)

    def boom(*a, **kw):
        raise llm.LLMError("connection refused")

    monkeypatch.setattr(llm, "complete", boom)
    r = post(client, body)
    assert r.status_code == 200
    d = r.json()
    assert d["llm_used"] is False
    assert d["class_summary"]["average_score_pct"] == 65.1
    assert d["misconceptions"]


# ---------------------------------------------------------------- помилки


def test_requires_key(client, body, mock_llm):
    r = post(client, body, headers={})
    assert r.status_code == 401
    assert r.json()["code"] == "unauthorized"


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda b: b["questions"][0].update(answer_key=["zzz"]), "answer_key"),
        (lambda b: b["students"].append(copy.deepcopy(b["students"][0])), "duplicate student_id"),
        (lambda b: b["questions"].append(copy.deepcopy(b["questions"][0])), "duplicate question id"),
        (lambda b: b["questions"][6].update(kind="single"), "exactly one key"),
    ],
)
def test_invalid_test(client, body, mock_llm, mutate, fragment):
    mutate(body)
    r = post(client, body)
    assert r.status_code == 422
    assert r.json()["code"] == "invalid_test"
    assert fragment in r.json()["message"]


def test_validation_error_does_not_echo_input(client, body, mock_llm):
    body["students"] = []
    r = post(client, body)
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"
    assert "input" not in json.dumps(r.json()["details"])


def test_overview_survives_split_misconceptions_from_model(client, body, fake_llm, monkeypatch):
    """MamayLM пише `"misconceptions": {"m1": {...}}, {"m2": {...}}` — висновок LLM не губиться."""
    good = llm.complete

    def broken(system, user, **kw):
        text = good(system, user, **kw)
        data = json.loads(text)
        ms = data.get("misconceptions")
        if not ms or len(ms) < 2:
            return text
        head = {k: v for k, v in data.items() if k != "misconceptions"}
        parts = [json.dumps({k: v}, ensure_ascii=False) for k, v in ms.items()]
        start = json.dumps(head, ensure_ascii=False)[:-1]
        return start + ', "misconceptions": ' + ", ".join(parts) + "}"

    monkeypatch.setattr(llm, "complete", broken)
    d = post(client, body).json()
    assert d["llm_used"] is True
    assert d["class_summary"]["overview"] == "Висновок для вчителя."
    assert d["misconceptions"] and all(m["title"] != "" for m in d["misconceptions"])
    assert any(m["title"] == "Додають знаменники" for m in d["misconceptions"])
