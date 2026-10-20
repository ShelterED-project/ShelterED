from fastapi import FastAPI, Depends, Form, Request
from datetime import datetime, timedelta
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import HTMLResponse
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

# 1. Головна сторінка (для учня)
@app.post("/roll-call")
def mark_roll_call(student_name: str = Form(...), db: Session = Depends(get_db)):
    new_entry = models.RollCall(student_name=student_name)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)

    return RedirectResponse(url="/", status_code=303)
# 2. Ендпоінт, який приймає ім'я учня
@app.post("/roll-call")
def mark_roll_call(student_name: str = Form(...), db: Session = Depends(get_db)):
    # Записуємо в базу
    new_entry = models.RollCall(student_name=student_name)
    db.add(new_entry)
    db.commit()
    db.refresh(new_entry)
    return {"status": "ok", "message": f"Учня {student_name} додано до списку"}


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    students = db.query(models.RollCall).all()

    for student in students:
        student.created_at = student.created_at + timedelta(hours=3)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"students": students}
    )