"""Кабінети (B14): дані з агрегатів, які рахує Celery (`app/services/stats.py`).

Вчитель — лише свої класи; учень — лише себе; батьки — лише свою дитину. Адміністрація
навчальних даних окремих учнів не бачить: її дашборд — тривоги школи й сумарне навчання під
час них (P2).
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Admin, CabinetStudent, Session, SettingsDep, TeacherClass
from app.api.stub import example_of
from app.schemas.errors import ErrorResponse
from app.schemas.stats import (
    AlertStudyOut,
    ClassGapsOut,
    ClassProgressOut,
    ClassTestsOut,
    KnowledgeMapOut,
    StudentProgressOut,
)
from app.services import stats as service

router = APIRouter(tags=["cabinets"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}


@router.get(
    "/classes/{class_id}/progress",
    response_model=ClassProgressOut,
    responses={200: example_of(ClassProgressOut), **ACCESS},
)
async def class_progress(klass: TeacherClass, session: Session) -> ClassProgressOut:
    """Прогрес класу по уроках (уроки розкладу з датою ≤ сьогодні): скільки учнів завершили
    урок, середній прогрес, результати тестів уроку. Лише вчитель цього класу."""
    return await service.class_progress(session, klass)


@router.get(
    "/classes/{class_id}/tests",
    response_model=ClassTestsOut,
    responses={200: example_of(ClassTestsOut), **ACCESS},
)
async def class_tests(
    klass: TeacherClass, session: Session, settings: SettingsDep
) -> ClassTestsOut:
    """Тести уроків класу зі статусом кожного учня: `passed` / `not_passed` / `closing_soon`
    (вікно закривається менш ніж за `STATS_CLOSING_SOON_H` год) / `pending`, з позначкою
    підозрілого часу пристрою. Лише вчитель цього класу."""
    return await service.class_tests(session, klass, settings)


@router.get(
    "/classes/{class_id}/gaps",
    response_model=ClassGapsOut,
    responses={200: example_of(ClassGapsOut), **ACCESS},
)
async def class_gaps(klass: TeacherClass, session: Session, settings: SettingsDep) -> ClassGapsOut:
    """Прогалини по темах (тема = урок): середня оцінка класу й частка правильних відповідей
    на кожне питання за зарахованими спробами. Лише вчитель цього класу."""
    return await service.class_gaps(session, klass, settings)


@router.get(
    "/students/{student_id}/progress",
    response_model=StudentProgressOut,
    responses={200: example_of(StudentProgressOut), **ACCESS},
)
async def student_progress(
    student: CabinetStudent, session: Session, settings: SettingsDep
) -> StudentProgressOut:
    """Прогрес учня по уроках, тести (з вікном і дедлайном), час навчання (усього й за 7 днів).
    Учень — себе, батьки — свою дитину, вчитель — учнів своїх класів. Статус переклички
    дитини — `GET /students/{id}/rollcall/current`."""
    return await service.student_progress(session, student, settings)


@router.get(
    "/students/{student_id}/knowledge-map",
    response_model=KnowledgeMapOut,
    responses={200: example_of(KnowledgeMapOut), **ACCESS},
)
async def knowledge_map(
    student: CabinetStudent, session: Session, settings: SettingsDep
) -> KnowledgeMapOut:
    """Мапа знань: по предметах — уроки завершено / усього, середня оцінка тестів, прогалина.
    Ті самі права, що й прогрес учня."""
    return await service.knowledge_map(session, student, settings)


@router.get(
    "/alerts/study",
    response_model=AlertStudyOut,
    responses={200: example_of(AlertStudyOut), **ACCESS},
)
async def alert_study(
    admin: Admin,
    session: Session,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AlertStudyOut:
    """Дашборд адміністрації (P2): тривоги своєї школи (найновіші першими, `from`/`to` — дати
    за поясом школи, включно) і скільки навчання на них припало — без даних окремих учнів.
    Агрегат перераховує beat раз на `STATS_REFRESH_INTERVAL_S`. Лише адміністрація."""
    return await service.alert_study(session, admin, date_from, date_to, limit)
