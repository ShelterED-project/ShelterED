import logging

import uvicorn

import config
from main import app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    print("Запуск сервера ShelterED...")
    print(f"Сторінка учня:   {config.STUDENT_URL}")
    print(f"Панель вчителя:  http://{config.HOTSPOT_HOST}:{config.LOCAL_PORT}/teacher")
    print("Не закривайте це вікно, поки триває урок!")
    # Передаємо об'єкт app, а не рядок "main:app" (так працює і в .exe)
    uvicorn.run(app, host="0.0.0.0", port=config.LOCAL_PORT)
