import uvicorn

if __name__ == "__main__":
    # Запускаємо сервер, доступний для всіх пристроїв у локальній мережі
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)