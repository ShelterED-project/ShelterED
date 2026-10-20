from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ShelterED Local Server")

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Локальний сервер працює"}

@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <html>
        <head>
            <title>ShelterED Local</title>
            <style>
                body { font-family: sans-serif; background-color: #1a1a1a; color: white; text-align: center; padding-top: 50px; }
                h1 { color: #fbbf24; }
            </style>
        </head>
        <body>
            <h1>Вітаємо в укритті!</h1>
            <p>Це локальний сервер ShelterED. Зв'язок з інтернетом не потрібен.</p>
        </body>
    </html>
    """
