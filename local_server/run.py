import os
import sys
import uvicorn
from main import app

# Цей блок потрібен, щоб PyInstaller знаходив папку templates всередині .exe
if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)

if __name__ == "__main__":
    print("Запуск сервера ShelterED...")
    print("Не закривайте це вікно, поки триває урок!")
    # Передаємо об'єкт app, а не рядок "main:app"
    uvicorn.run(app, host="0.0.0.0", port=8000)