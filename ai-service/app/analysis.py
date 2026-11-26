"""Аналіз тесту класу: POST /ai/v1/test-analysis.

Поділ відповідальності:
- КОД рахує все, що можна порахувати: оцінки, частку правильних відповідей,
  які хибні варіанти обирали й хто саме, групи учнів. Це детерміновано й перевірювано.
- LLM лише формулює слова: назви вмінь, пояснення типових помилок, висновок
  і рекомендації для вчителя, поради учню й батькам.
- У LLM іде тільки знеособлена статистика класу: жодного student_id, жодних відповідей
  конкретного учня. LLM не може «вигадати» факт про дитину, бо нічого про неї не знає.
- LLM недоступна → відповідь однаково повертається зі статистикою й шаблонними текстами
  (llm_used=false). Вчитель не лишається з помилкою замість результату.
"""

import asyncio
import logging
import math
from collections import defaultdict
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.llm import LLMError, complete_json
from app.schemas import (
    TAClassSummary,
    TAEvidence,
    TAFeedback,
    TAMisconception,
    TAQuestion,
    TAQuestionStat,
    TASkill,
    TAStudentResult,
    TAWrongAnswer,
    TestAnalysisRequest,
    TestAnalysisResponse,
)

logger = logging.getLogger("ai-service.analysis")

# Типова помилка: той самий хибний варіант обрали щонайменше 2 учні і ≥ 10% класу
MISCONCEPTION_MIN_COUNT = 2
MISCONCEPTION_MIN_SHARE = 0.10
MAX_MISCONCEPTIONS = 8
QUESTIONS_PER_LLM_CALL = 8
MAX_ITEMS_IN_FEEDBACK = 3
STRONG_SCORE_PCT = 85.0


class InvalidTestError(ValueError):
    """Тест суперечливий: ключ не з варіантів, дублікати id тощо (HTTP 422 invalid_test)."""


# ---------------------------------------------------------------- підрахунки


def _status(pct: float) -> str:
    if pct < 50:
        return "critical"
    if pct < 75:
        return "attention"
    return "ok"


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def validate(req: TestAnalysisRequest) -> None:
    qids = [q.id for q in req.questions]
    if len(set(qids)) != len(qids):
        raise InvalidTestError("duplicate question id")
    sids = [s.student_id for s in req.students]
    if len(set(sids)) != len(sids):
        raise InvalidTestError("duplicate student_id")
    for q in req.questions:
        oids = [o.id for o in q.options]
        if len(set(oids)) != len(oids):
            raise InvalidTestError(f"question {q.id}: duplicate option id")
        if not set(q.answer_key) <= set(oids):
            raise InvalidTestError(f"question {q.id}: answer_key is not among options")
        if q.kind == "single" and len(set(q.answer_key)) != 1:
            raise InvalidTestError(f"question {q.id}: single question needs exactly one key")


def _option_text(q: TAQuestion, ids: Tuple[str, ...]) -> str:
    texts = {o.id: o.text for o in q.options}
    return "; ".join(texts.get(i, i) for i in ids) if ids else "без відповіді"


def compute(req: TestAnalysisRequest) -> Dict[str, Any]:
    """Уся статистика без LLM. Зарахування як у backend: множина обраних == ключ."""
    total_students = len(req.students)
    total_points = sum(q.points for q in req.questions)

    per_q: Dict[str, Dict[str, Any]] = {}
    for pos, q in enumerate(req.questions, start=1):
        per_q[q.id] = {
            "q": q,
            "position": pos,
            "key": frozenset(q.answer_key),
            "correct": [],
            "answered": 0,
            "wrong": defaultdict(list),  # tuple(обрані id) -> [student_id]
        }

    students: List[Dict[str, Any]] = []
    for s in req.students:
        earned, correct_q, wrong_q, chosen_wrong = 0, [], [], {}
        for q in req.questions:
            st = per_q[q.id]
            chosen = tuple(sorted(set(s.answers.get(q.id) or [])))
            if chosen:
                st["answered"] += 1
            if chosen and frozenset(chosen) == st["key"]:
                earned += q.points
                correct_q.append(q.id)
                st["correct"].append(s.student_id)
            else:
                wrong_q.append(q.id)
                st["wrong"][chosen].append(s.student_id)
                chosen_wrong[q.id] = chosen
        score = _pct(earned, total_points)
        students.append(
            {
                "id": s.student_id,
                "score": score,
                "correct": correct_q,
                "wrong": wrong_q,
                "chosen_wrong": chosen_wrong,
            }
        )

    # Типові помилки: однаковий хибний (непорожній) вибір у кількох учнів
    candidates = []
    for qid, st in per_q.items():
        for chosen, sids in st["wrong"].items():
            if not chosen:
                continue
            if len(sids) >= MISCONCEPTION_MIN_COUNT and len(sids) / total_students >= MISCONCEPTION_MIN_SHARE:
                candidates.append((len(sids), st["position"], qid, chosen, sids))
    candidates.sort(key=lambda c: (-c[0], c[1]))
    misconceptions = [
        {
            "id": f"m{i}",
            "question_id": qid,
            "option_ids": list(chosen),
            "student_ids": list(sids),
            "count": count,
            "share_pct": _pct(count, total_students),
        }
        for i, (count, _, qid, chosen, sids) in enumerate(candidates[:MAX_MISCONCEPTIONS], start=1)
    ]

    return {
        "per_q": per_q,
        "students": students,
        "misconceptions": misconceptions,
        "total_students": total_students,
        "average": round(sum(s["score"] for s in students) / total_students, 1),
        "passed": sum(1 for s in students if s["score"] >= req.pass_score_pct),
    }


# ---------------------------------------------------------------- LLM


def _context(req: TestAnalysisRequest) -> str:
    parts = [f"{req.grade} клас"]
    if req.subject:
        parts.append(f"предмет «{req.subject}»")
    if req.lesson_title:
        parts.append(f"тема уроку «{req.lesson_title}»")
    if req.test_title:
        parts.append(f"тест «{req.test_title}»")
    return ", ".join(parts)


def _q_block(q: TAQuestion, label: str, correct_pct: float) -> str:
    opts = "\n".join(
        f"   {o.id}) {o.text}{'  ← правильна' if o.id in q.answer_key else ''}" for o in q.options
    )
    return f"{label}. {q.prompt}\n{opts}\n   Правильно відповіли: {correct_pct:.0f}% класу"


def _skills_call(req: TestAnalysisRequest, items: List[Tuple[str, TAQuestion, float]]) -> Dict[str, Any]:
    labels = [label for label, _, _ in items]
    system = "\n".join(
        [
            f"Ти — методист, який допомагає вчителю розібрати результати тесту ({_context(req)}).",
            "Для кожного питання дай:",
            "- skill: коротка назва вміння, яке перевіряє питання (2–6 слів, з великої літери,"
            " без слова «вміння»). Питання на одне вміння отримують однакову назву.",
            f"- student_tip: порада учню {req.grade} класу, що повторити й на що звернути увагу"
            " (1–2 речення, до 160 символів, звертання на «ти», доброзичливо, без оцінок).",
            "- parent_tip: як батькам допомогти дитині вдома з цим (1 речення, до 130 символів,"
            " звертання на «ви», без шкільних термінів, яких батьки можуть не знати).",
            "Пиши українською. Не вигадуй фактів поза питанням.",
            'Формат: {"q1": {"skill": "...", "student_tip": "...", "parent_tip": "..."}, ...}'
            f" — ключі рівно: {', '.join(labels)}.",
        ]
    )
    user = "\n\n".join(_q_block(q, label, pct) for label, q, pct in items)

    def finalize(data: Dict[str, Any]) -> None:
        for label in labels:
            v = data.get(label)
            if not isinstance(v, dict) or not str(v.get("skill") or "").strip():
                raise ValueError(f"no skill for {label}")
            for k in ("skill", "student_tip", "parent_tip"):
                v[k] = str(v.get(k) or "").strip()

    return complete_json(
        system,
        user,
        kind="explain",
        temperature=0.2,
        max_tokens=250 * len(items) + 200,
        finalize=finalize,
        timeout=settings.LLM_ANALYSIS_TIMEOUT,
    )


def _collect_misconceptions(data: Dict[str, Any], mids: List[str]) -> Dict[str, Any]:
    """`misconceptions` як об'єкт {m1: {...}}. Моделі буває повертають інакше: список
    `[{"m1": {...}}, {"m2": {...}}]` або `[{"id": "m1", ...}]`, чи `m2…` на верхньому рівні
    (після ремонту JSON у llm.py) — збираємо все в один об'єкт."""
    raw = data.get("misconceptions") or {}
    ms: Dict[str, Any] = {}
    if isinstance(raw, dict):
        ms.update(raw)
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("id"), str):
                ms[item["id"]] = item
            else:
                ms.update({k: v for k, v in item.items() if isinstance(v, dict)})
    else:
        raise ValueError("misconceptions is not an object")
    for mid in mids:
        if mid not in ms and isinstance(data.get(mid), dict):
            ms[mid] = data.pop(mid)
    return ms


def _overview_call(req: TestAnalysisRequest, stats: Dict[str, Any]) -> Dict[str, Any]:
    per_q = stats["per_q"]
    q_lines = []
    for st in per_q.values():
        q = st["q"]
        pct = _pct(len(st["correct"]), stats["total_students"])
        q_lines.append(
            f"Питання {st['position']}: {q.prompt[:200]} | правильна відповідь: "
            f"«{_option_text(q, tuple(sorted(q.answer_key)))}» | правильно: {pct:.0f}%"
        )
    m_lines = []
    for m in stats["misconceptions"]:
        st = per_q[m["question_id"]]
        q = st["q"]
        m_lines.append(
            f"{m['id']}: питання {st['position']} «{q.prompt[:200]}». Правильно: "
            f"«{_option_text(q, tuple(sorted(q.answer_key)))}», а {m['count']} учнів "
            f"({m['share_pct']:.0f}%) обрали «{_option_text(q, tuple(m['option_ids']))}»."
        )
    mids = [m["id"] for m in stats["misconceptions"]]

    system = "\n".join(
        [
            f"Ти — досвідчений методист. Готуєш для вчителя висновок за результатами тесту ({_context(req)}).",
            "Дані знеособлені й агреговані. Використовуй лише наведені числа, нічого не вигадуй.",
            "Поля відповіді:",
            "- overview: висновок для вчителя, 3–5 речень: що клас засвоїв, де найбільше відстає,"
            " яка головна причина помилок і з чого почати наступний урок.",
            "- recommendations: 2–4 конкретні дії для вчителя на наступний урок (кожна — одне речення).",
            "- misconceptions: для кожної типової помилки — title (суть хибного уявлення, до 70 символів,"
            " напр. «Додають знаменники разом із чисельниками»), teacher (чому учні так помиляються"
            f" і як це розібрати, 1–2 речення), student_tip (порада учню {req.grade} класу на «ти»,"
            " як не помилятися, 1–2 речення, до 160 символів).",
            "Пиши українською, коротко й по-діловому.",
            'Формат: {"overview": "...", "recommendations": ["..."], "misconceptions": {"m1": '
            '{"title": "...", "teacher": "...", "student_tip": "..."}}}'
            + (f" — ключі misconceptions рівно: {', '.join(mids)}." if mids else " — misconceptions: {}."),
        ]
    )
    user = "\n".join(
        [
            f"Учнів, що написали тест: {stats['total_students']}. Середній результат: {stats['average']:.0f}%."
            f" Склали (≥ {req.pass_score_pct:.0f}%): {stats['passed']}.",
            "",
            "Питання:",
            *q_lines,
            "",
            "Типові помилки:" if m_lines else "Типових помилок (однакова хибна відповідь у кількох учнів) немає.",
            *m_lines,
        ]
    )

    def finalize(data: Dict[str, Any]) -> None:
        if not str(data.get("overview") or "").strip():
            raise ValueError("no overview")
        data["overview"] = str(data["overview"]).strip()
        recs = data.get("recommendations") or []
        data["recommendations"] = [str(r).strip() for r in recs if str(r).strip()][:4]
        ms = _collect_misconceptions(data, mids)
        for mid in mids:
            v = ms.get(mid)
            if not isinstance(v, dict) or not str(v.get("title") or "").strip():
                raise ValueError(f"no title for {mid}")
            for k in ("title", "teacher", "student_tip"):
                v[k] = str(v.get(k) or "").strip()
        data["misconceptions"] = ms

    return complete_json(
        system,
        user,
        kind="explain",
        temperature=0.3,
        max_tokens=700 + 220 * len(mids),
        finalize=finalize,
        timeout=settings.LLM_ANALYSIS_TIMEOUT,
    )


def _chunks(items: List[Any], size: int) -> List[List[Any]]:
    """Рівні частини, не більші за size: 10 питань → 5 + 5, а не 8 + 2."""
    n = max(1, math.ceil(len(items) / size))
    k = math.ceil(len(items) / n)
    return [items[i : i + k] for i in range(0, len(items), k)]


async def _llm(req: TestAnalysisRequest, stats: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], bool]:
    """Паралельні виклики LLM. Повертає (поради за question_id, огляд або None, чи щось вдалося)."""
    if settings.MOCK_LLM:
        return {}, None, False

    items = [
        (f"q{st['position']}", st["q"], _pct(len(st["correct"]), stats["total_students"]))
        for st in stats["per_q"].values()
    ]
    chunks = _chunks(items, QUESTIONS_PER_LLM_CALL)
    calls = [asyncio.to_thread(partial(_skills_call, req, chunk)) for chunk in chunks]
    calls.append(asyncio.to_thread(partial(_overview_call, req, stats)))
    results = await asyncio.gather(*calls, return_exceptions=True)

    tips: Dict[str, Any] = {}
    ok = False
    for chunk, res in zip(chunks, results[:-1]):
        if isinstance(res, Exception):
            logger.warning("test-analysis skills call failed: %s", res)
            continue
        ok = True
        for label, q, _ in chunk:
            tips[q.id] = res[label]
    overview = results[-1]
    if isinstance(overview, Exception):
        logger.warning("test-analysis overview call failed: %s", overview)
        overview = None
    else:
        ok = True
    for res in results:
        if isinstance(res, Exception) and not isinstance(res, LLMError):
            logger.error("unexpected error in test-analysis LLM call", exc_info=res)
    return tips, overview, ok


# ---------------------------------------------------------------- збирання відповіді

_FALLBACK_STUDENT_TIP = "Переглянь ще раз матеріал уроку до цього питання і спробуй схоже завдання з AI-репетитором."
_FALLBACK_PARENT_TIP = "Попросіть дитину пояснити вам ці питання своїми словами — так видно, де саме складно."


def _short(req: TestAnalysisRequest, qid: str, limit: int = 80) -> str:
    prompt = next(q.prompt for q in req.questions if q.id == qid).strip()
    return prompt if len(prompt) <= limit else prompt[: limit - 1].rstrip() + "…"


def _join(items: List[str]) -> str:
    return ", ".join(items)


def _student_text(req, s, skills_of, tips, m_by_student, m_info, total_q, named) -> str:
    n_ok = len(s["correct"])
    if not s["wrong"]:
        return "Усі відповіді правильні — чудова робота! 🎉 Так тримати."
    lines = [f"Правильних відповідей: **{n_ok} з {total_q}**."]
    if named and s["strong_skills"]:
        lines.append(f"Добре виходить: {_join(s['strong_skills'][:3])}. 👍")
    lines += ["", "Варто повторити:"]
    seen_skills, seen_tips = set(), set()
    for qid in s["wrong"]:
        skill = skills_of[qid]
        if skill in seen_skills:
            continue
        seen_skills.add(skill)
        label = skill if named else f"Питання {skill.split()[-1]}: «{_short(req, qid)}»"
        mid = m_by_student.get((s["id"], qid))
        tip = (m_info.get(mid) or {}).get("student_tip") if mid else None
        tip = tip or tips.get(qid, {}).get("student_tip") or _FALLBACK_STUDENT_TIP
        if tip in seen_tips:  # одна порада на кілька вмінь (та сама помилка) — не повторюємо
            lines.append(f"- **{label}**")
        else:
            seen_tips.add(tip)
            lines.append(f"- **{label}** — {tip}")
        if len(seen_skills) >= MAX_ITEMS_IN_FEEDBACK:
            break
    lines += ["", "Якщо щось незрозуміло, спитай AI-репетитора: він пояснить інакше. Ти впораєшся! 💪"]
    return "\n".join(lines)


def _parent_text(req, s, tips, total_q, named) -> str:
    title = f"«{req.test_title}»" if req.test_title else "з уроку"
    topic = f" (тема «{req.lesson_title}»)" if req.lesson_title else ""
    n_ok = len(s["correct"])
    lines = [f"Тест {title}{topic}: правильних відповідей **{n_ok} з {total_q}** ({s['score']:.0f}%)."]
    if not s["wrong"]:
        lines.append("Усі відповіді правильні. Похваліть дитину — це мотивує! 🎉")
        return "\n".join(lines)
    if named:
        if s["strong_skills"]:
            lines.append(f"Добре виходить: {_join(s['strong_skills'][:3])}.")
        lines.append(f"Варто повторити разом: {_join(s['weak_skills'][:MAX_ITEMS_IN_FEEDBACK])}.")
    else:
        nums = ", ".join(skill.split()[-1] for skill in dict.fromkeys(s["weak_skills"]))
        lines.append(f"Варто повторити разом питання тесту: {nums}.")
    lines += ["", "Як допомогти вдома:"]
    seen_tips: List[str] = []
    for qid in s["wrong"]:
        tip = tips.get(qid, {}).get("parent_tip") or _FALLBACK_PARENT_TIP
        if tip not in seen_tips:
            seen_tips.append(tip)
        if len(seen_tips) >= 2:
            break
    lines += [f"- {t}" for t in seen_tips]
    return "\n".join(lines)


def _teacher_text(s, per_q, m_by_student, m_info, total_q, needs_support, named) -> str:
    parts = [f"**{s['score']:.0f}%** ({len(s['correct'])}/{total_q})."]
    if s["wrong"]:
        nums = ", ".join(str(per_q[qid]["position"]) for qid in s["wrong"])
        parts.append(f"Помилки в питаннях: {nums}.")
        titles: List[str] = []
        for qid in s["wrong"]:
            mid = m_by_student.get((s["id"], qid))
            if mid and m_info[mid]["title"] not in titles:
                titles.append(m_info[mid]["title"])
        if titles:
            parts.append("Типові помилки: " + "; ".join(titles) + ".")
        if named:
            parts.append(f"Слабкі місця: {_join(s['weak_skills'])}.")
    else:
        parts.append("Без помилок.")
    if needs_support:
        parts.append("⚠️ Потребує підтримки.")
    return " ".join(parts)


async def analyze(req: TestAnalysisRequest) -> TestAnalysisResponse:
    validate(req)
    stats = compute(req)
    tips, overview, llm_ok = await _llm(req, stats)

    per_q = stats["per_q"]
    total = stats["total_students"]
    total_q = len(req.questions)

    # Назви вмінь (від LLM або «Питання N»)
    skills_of = {
        qid: (tips.get(qid, {}).get("skill") or f"Питання {st['position']}") for qid, st in per_q.items()
    }
    named = bool(tips)  # є справжні назви вмінь (інакше не пишемо «Добре виходить: Питання 1»)

    # Питання
    questions_out = []
    for qid, st in per_q.items():
        q = st["q"]
        correct_pct = _pct(len(st["correct"]), total)
        wrong = sorted(st["wrong"].items(), key=lambda kv: (-len(kv[1]), kv[0]))
        questions_out.append(
            TAQuestionStat(
                question_id=qid,
                position=st["position"],
                skill=skills_of[qid],
                correct_pct=correct_pct,
                correct_count=len(st["correct"]),
                answered_count=st["answered"],
                status=_status(correct_pct),
                wrong_answers=[
                    TAWrongAnswer(
                        option_ids=list(chosen),
                        option_text=_option_text(q, chosen),
                        count=len(sids),
                        student_ids=sids,
                    )
                    for chosen, sids in wrong
                ],
            )
        )

    # Вміння класу: агрегуємо питання з однаковою назвою (зважено за балами)
    skill_q: Dict[str, List[str]] = defaultdict(list)
    for qid in per_q:
        skill_q[skills_of[qid]].append(qid)
    skills_out = []
    for skill, qids in skill_q.items():
        pts = sum(per_q[q]["q"].points for q in qids)
        got = sum(per_q[q]["q"].points * len(per_q[q]["correct"]) for q in qids)
        pct = _pct(got, pts * total)
        skills_out.append(TASkill(skill=skill, question_ids=qids, correct_pct=pct, status=_status(pct)))
    skills_out.sort(key=lambda sk: sk.correct_pct)

    # Типові помилки: сирі (питання + хибний варіант) → об'єднані за однаковою назвою від LLM
    llm_m = (overview or {}).get("misconceptions") or {}
    groups: Dict[str, Dict[str, Any]] = {}
    raw_to_group: Dict[str, str] = {}
    for m in stats["misconceptions"]:
        st = per_q[m["question_id"]]
        q = st["q"]
        wrong_text = _option_text(q, tuple(m["option_ids"]))
        right_text = _option_text(q, tuple(sorted(q.answer_key)))
        info = llm_m.get(m["id"]) or {}
        title = info.get("title") or f"Питання {st['position']}: обирають «{wrong_text}» замість «{right_text}»"
        norm = " ".join(title.lower().replace("«", "").replace("»", "").strip(" .!").split())
        g = groups.get(norm)
        if g is None:
            g = groups[norm] = {
                "id": m["id"],
                "title": title,
                "teacher": info.get("teacher")
                or f"{m['count']} учнів ({m['share_pct']:.0f}%) обрали однакову хибну відповідь. Варто розібрати це питання з класом.",
                "student_tip": info.get("student_tip") or "",
                "question_ids": [],
                "student_ids": [],
                "evidence": [],
            }
        raw_to_group[m["id"]] = g["id"]
        if m["question_id"] not in g["question_ids"]:
            g["question_ids"].append(m["question_id"])
        g["student_ids"] += [sid for sid in m["student_ids"] if sid not in g["student_ids"]]
        g["evidence"].append(
            TAEvidence(question_id=m["question_id"], option_ids=m["option_ids"], option_text=wrong_text, count=m["count"])
        )

    m_info: Dict[str, Dict[str, Any]] = {g["id"]: g for g in groups.values()}
    m_by_student: Dict[Tuple[str, str], str] = {}
    for m in stats["misconceptions"]:
        for sid in m["student_ids"]:
            m_by_student[(sid, m["question_id"])] = raw_to_group[m["id"]]
    misconceptions_out = sorted(
        (
            TAMisconception(
                id=g["id"],
                title=g["title"],
                explanation=g["teacher"],
                question_ids=sorted(g["question_ids"], key=lambda qid: per_q[qid]["position"]),
                student_ids=g["student_ids"],
                share_pct=_pct(len(g["student_ids"]), total),
                evidence=g["evidence"],
            )
            for g in groups.values()
        ),
        key=lambda m: -len(m.student_ids),
    )

    # Учні
    students_out = []
    needs_support_ids = []
    for s in stats["students"]:
        weak = list(dict.fromkeys(skills_of[q] for q in s["wrong"]))
        strong = [sk for sk in dict.fromkeys(skills_of[q] for q in s["correct"]) if sk not in weak]
        s["weak_skills"], s["strong_skills"] = weak, strong
        passed = s["score"] >= req.pass_score_pct
        if not passed:
            status = "needs_support"
            needs_support_ids.append(s["id"])
        elif s["score"] >= STRONG_SCORE_PCT:
            status = "strong"
        else:
            status = "ok"
        mids = list(dict.fromkeys(m_by_student[(s["id"], q)] for q in s["wrong"] if (s["id"], q) in m_by_student))
        students_out.append(
            TAStudentResult(
                student_id=s["id"],
                score_pct=s["score"],
                passed=passed,
                status=status,
                correct_question_ids=s["correct"],
                wrong_question_ids=s["wrong"],
                strong_skills=strong,
                weak_skills=weak,
                misconception_ids=mids,
                feedback=TAFeedback(
                    teacher=_teacher_text(s, per_q, m_by_student, m_info, total_q, not passed, named),
                    student=_student_text(req, s, skills_of, tips, m_by_student, m_info, total_q, named),
                    parent=_parent_text(req, s, tips, total_q, named),
                ),
            )
        )

    # Висновок для вчителя
    if overview:
        overview_text = overview["overview"]
        recommendations = overview["recommendations"]
    else:
        weakest = [sk for sk in skills_out if sk.status != "ok"][:3]
        overview_text = (
            f"Середній результат класу — {stats['average']:.0f}%, тест склали {stats['passed']} з {total}."
            + (
                " Найбільше відстають: " + _join(f"{sk.skill} ({sk.correct_pct:.0f}%)" for sk in weakest) + "."
                if weakest
                else " Усі вміння засвоєні на достатньому рівні."
            )
        )
        recommendations = []
        if misconceptions_out:
            recommendations.append(f"Розберіть із класом типову помилку: {misconceptions_out[0].title}.")
        if weakest:
            recommendations.append(f"Почніть наступний урок із повторення: {weakest[0].skill}.")
        if needs_support_ids:
            recommendations.append(
                f"Учням, які не склали тест ({len(needs_support_ids)}), запропонуйте повторити тему з AI-репетитором."
            )

    return TestAnalysisResponse(
        class_summary=TAClassSummary(
            students_total=total,
            average_score_pct=stats["average"],
            passed_count=stats["passed"],
            pass_score_pct=req.pass_score_pct,
            needs_support_ids=needs_support_ids,
            overview=overview_text,
            recommendations=recommendations,
        ),
        skills=skills_out,
        questions=questions_out,
        misconceptions=misconceptions_out,
        students=students_out,
        llm_used=llm_ok,
    )
