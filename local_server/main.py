from fastapi import FastAPI, Depends, Form, Request
from datetime import datetime, timedelta
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import database, models , pytz
import qrcode
from io import BytesIO
from fastapi.responses import StreamingResponse
import uuid

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="ShelterED Local Server")

# Налаштовуємо папку для HTML-шаблонів
templates = Jinja2Templates(directory="templates")

# Функція для підключення до БД
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1. Головна сторінка (для вчителя/учня)
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    students = db.query(models.RollCall).all()


    for student in students:
        kyiv_tz = pytz.timezone('Europe/Kyiv')
        for student in students:
            # Робимо час "обізнаним" про часовий пояс (UTC), а потім переводимо в Київ
            utc_time = pytz.utc.localize(student.created_at)
            kyiv_time = utc_time.astimezone(kyiv_tz)
            student.created_at = kyiv_time

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"students": students}
    )

# 2. Ендпоінт для прийому імені
# Генеруємо ID сесії один раз при запуску сервера
CURRENT_SESSION_ID = str(uuid.uuid4())

@app.post("/roll-call")
def mark_roll_call(student_name: str = Form(...), db: Session = Depends(get_db)):
    new_entry = models.RollCall(
        student_name=student_name,
        status="in_shelter",
        session_id=CURRENT_SESSION_ID
    )
    db.add(new_entry)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Локальний сервер працює"}


@app.get("/teacher", response_class=HTMLResponse)
def teacher_dashboard(request: Request, db: Session = Depends(get_db)):
    students = db.query(models.RollCall).all()

    # Перетворюємо час на київський
    for student in students:
        kyiv_tz = pytz.timezone('Europe/Kyiv')
        for student in students:
            # Робимо час "обізнаним" про часовий пояс (UTC), а потім переводимо в Київ
            utc_time = pytz.utc.localize(student.created_at)
            kyiv_time = utc_time.astimezone(kyiv_tz)
            student.created_at = kyiv_time

    return templates.TemplateResponse(
        request=request,
        name="teacher.html",
        context={"students": students}
    )

@app.get("/qr")
def generate_qr():
    # Генеруємо QR-код з адресою для учнів
    img = qrcode.make("http://192.168.137.1:8000")
    buf = BytesIO()
    img.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")