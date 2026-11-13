import joblib
from sklearn.svm import LinearSVC
from sentence_transformers import SentenceTransformer

print("Завантаження моделі ембеддингів...")
embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Навчальні дані для інтент-роутера ShelterED
texts = [
    # explain (пояснення теорії, правил)
    "поясни правило",
    "що таке фотосинтез",
    "не розумію цю тему з фізики",
    "розкажи простими словами про дроби",
    # practice (практика, задачі, приклади)
    "дай задачу",
    "хочу попрактикуватись",
    "як це розв'язати",
    # check (перевірка відповіді)
    "перевір мою відповідь",
    "чи правильно я розв'язав",
    # support (емоційна підтримка / тривога)
    "мені тривожно",
    "я втомився",
    "страшно через сирену",
    # chat (загальна розмова)
    "привіт",
    "як справи",
]

labels = [
    "explain",
    "explain",
    "explain",
    "explain",
    "practice",
    "practice",
    "practice",
    "check",
    "check",
    "support",
    "support",
    "support",
    "chat",
    "chat",
]

print("Векторизація текстів...")
X = embedder.encode(texts)

print("Навчання класифікатора LinearSVC...")
classifier = LinearSVC()
classifier.fit(X, labels)

# Зберігаємо і ембедер, і класифікатор в один файл
model_data = {"embedder": embedder, "classifier": classifier}
joblib.dump(model_data, "shelter_router.pkl")

print("Модель успішно натренована і збережена у файл shelter_router.pkl!")

# Швидка перевірка (тест)
test_queries = ["як розв'язати це рівняння?", "мені дуже тривожно", "дай приклад для практики"]
test_embeddings = embedder.encode(test_queries)
predictions = classifier.predict(test_embeddings)

print("\nРезультати тесту:")
for q, p in zip(test_queries, predictions):
  print(f"Питання: '{q}' --> Інтент: {p}")