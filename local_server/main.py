from fastapi import FastAPI, Depends, Form, Request
from datetime import datetime, timedelta
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import database, models

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

    # Додаємо 3 години для київського часу
    for student in students:
        student.created_at = student.created_at + timedelta(hours=3)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"students": students}
    )

# 2. Ендпоінт для прийому імені
@app.post("/roll-call")
def mark_roll_call(student_name: str = Form(...), db: Session = Depends(get_db)):
    new_entry = models.RollCall(student_name=student_name)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    # Перенаправляємо користувача назад на головну сторінку
    return RedirectResponse(url="/", status_code=303)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Локальний сервер працює"}