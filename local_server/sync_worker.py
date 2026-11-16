import time
import requests
import json
from datetime import datetime
import database, models
from sqlalchemy.orm import Session

#  URL
API_URL = "http://127.0.0.1:8000"


def sync_data():
    print("Фонова синхронізація запущена...")
    while True:
        db = database.SessionLocal()
        try:
            # Беремо всі несинхронізовані записи
            unsynced_records = db.query(models.RollCall).filter(models.RollCall.is_synced == False).all()

            if unsynced_records:
                events = []
                for record in unsynced_records:
                    # Формуємо подію за схемою
                    events.append({
                        "client_event_id": record.client_event_id,
                        "type": "rollcall_status",
                        "device_id": str(record.client_event_id),  # Тимчасово використовуємо цей же ID
                        "occurred_at": record.created_at.isoformat() + "Z",
                        "payload": {
                            "session_id": record.session_id,
                            "status": "in_shelter"
                        }
                    })

                payload = {
                    "sent_at": datetime.utcnow().isoformat() + "Z",
                    "events": events
                }

                # Відправляємо (тут потрібен JWT токен)
                try:
                    response = requests.post(f"{API_URL}/sync/events", json=payload, timeout=5)

                    if response.status_code == 200:
                        print(f"Успішно синхронізовано {len(events)} подій!")
                        # Позначаємо як синхронізовані
                        for record in unsynced_records:
                            record.is_synced = True
                        db.commit()
                    else:
                        print(f"Помилка синхронізації: {response.status_code} - {response.text}")
                except requests.exceptions.RequestException as e:
                    print(f"Немає зв'язку з хмарою: {e}")
                    # Якщо інтернету немає, просто чекаємо далі
                    pass
        finally:
            db.close()

        # Чекаємо 60 секунд перед наступною перевіркою
        time.sleep(60)


if __name__ == "__main__":
    sync_data()