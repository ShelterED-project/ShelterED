"""Розбір JSON від LLM: типові помилки моделей лагодяться, а не ламають виклик."""
import pytest

from app.llm import _extract_json


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": [1, 2]}\n```', {"a": [1, 2]}),
        ('Ось відповідь: {"a": 1} Сподіваюсь, допоміг {:)}', {"a": 1}),
        # кома перед закриваючою дужкою (саме так ламає MamayLM / Gemma)
        ('{"overview": "Текст", "recommendations": ["x", "y",], "misconceptions": {"m1": {"title": "t"},},}',
         {"overview": "Текст", "recommendations": ["x", "y"], "misconceptions": {"m1": {"title": "t"}}}),
        ('{"a": 1, // коментар\n "b": 2 /* ще */}', {"a": 1, "b": 2}),
        ('{"a": "рядок\nз переносом"}', {"a": "рядок\nз переносом"}),
        # кома й дужки всередині рядка не чіпаються
        ('{"a": "кома ,} всередині // і не коментар",}', {"a": "кома ,} всередині // і не коментар"}),
        ('{"a": "лапки \\" екрановані",}', {"a": 'лапки " екрановані'}),
    ],
)
def test_extract_json_repairs_common_llm_mistakes(raw, expected):
    assert _extract_json(raw) == expected


@pytest.mark.parametrize("raw", ["немає json", '{"a": }', "[1, 2]"])
def test_extract_json_still_rejects_garbage(raw):
    with pytest.raises(ValueError):
        _extract_json(raw)


# Справжній уривок MamayLM (лог docker): модель закриває `misconceptions` після m1 і пише
# кожну наступну помилку окремим об'єктом через кому.
MAMAY = (
    '{"overview": "Клас загалом засвоїв тему.", "recommendations": ["Повторити -s"], '
    '"misconceptions": {"m1": {"title": "Плутають always і never", "teacher": "t", '
    '"student_tip": "Never – «ніколи», always – «завжди». Звертай увагу на значення слів, '
    'коли читаєш або пишеш речення."}}, {"m2": {"title": "Не додають закінчення -s", '
    '"teacher": "t2", "student_tip": "s2"}}, {"m3": {"title": "Т3", "teacher": "t3", "student_tip": "s3"}}'
)


@pytest.mark.parametrize("tail", ["}", "", "}}"])  # як модель закінчує: є/нема/зайва `}`
def test_split_misconceptions_are_recovered(tail):
    data = _extract_json(MAMAY + tail)
    assert data["overview"] == "Клас загалом засвоїв тему."
    assert data["misconceptions"]["m1"]["title"] == "Плутають always і never"
    # m2, m3 після ремонту — на верхньому рівні; analysis._collect_misconceptions їх збирає
    from app.analysis import _collect_misconceptions

    ms = _collect_misconceptions(data, ["m1", "m2", "m3"])
    assert [ms[m]["title"] for m in ("m1", "m2", "m3")] == [
        "Плутають always і never",
        "Не додають закінчення -s",
        "Т3",
    ]


def test_misconceptions_as_list_are_merged():
    from app.analysis import _collect_misconceptions

    data = {"misconceptions": [{"m1": {"title": "a"}}, {"id": "m2", "title": "b"}]}
    ms = _collect_misconceptions(data, ["m1", "m2"])
    assert ms["m1"]["title"] == "a" and ms["m2"]["title"] == "b"
