import joblib

# Завантажуємо збережену модель
model_data = joblib.load("shelter_router.pkl")
embedder = model_data["embedder"]
classifier = model_data["classifier"]

# Тестуємо на новій фразі
user_query = ["поясни як додавати дроби"]
embedding = embedder.encode(user_query)
intent = classifier.predict(embedding)[0]

print(f"Визначений інтент: {intent}")  # Виведе щось на кшталт 'explain'