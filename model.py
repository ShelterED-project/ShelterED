import joblib
from sentence_transformers import SentenceTransformer
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# 1. Навчальні дані для 5 інтентів ShelterED
texts = [
    # --- explain (пояснення теорії, правил) ---
    "поясни правило",
    "що таке фотосинтез",
    "не розумію цю тему з фізики",
    "розкажи простими словами про дроби",
    "як працює цикл for в python",
    "що означає цей термін",
    "не можу зрозуміти закон ома",
    "поясни будь ласка теорему піфагора",

    # --- practice (практика, задачі, приклади) ---
    "дай задачу",
    "хочу попрактикуватись",
    "як це розв'язати",
    "накинь приклад на практику",
    "дай якесь завдання по програмуванню",
    "хочу закріпити тему вправами",
    "підкинь задачу на цикли",

    # --- check (перевірка рішень учня) ---
    "перевір мою відповідь",
    "це правильно?",
    "ось що в мене вийшло, подивись",
    "чи вірне таке розв'язання",
    "перевір код чи є тут помилки",
    "скажи чи я правильно порахував",

    # --- support (психологічна підтримка, вигорання) ---
    "я втомився",
    "мені тривожно перед іспитом",
    "не можу більше, здаюсь",
    "паніка, нічого не встигаю",
    "я занадто тупий для цього",
    "у мене вигорання, не хочу нічого робити",
    "мені сумно і важко",

    # --- chat (загальні розмови, цікаві факти) ---
    "а чому чорні діри такі масивні",
    "як працює штучний інтелект",
    "розкажи цікавий факт про космос",
    "що буде якщо впасти в чорну діру",
    "як винайшли комп'ютер",
    "який сьогодні день тижня"
]

labels = [
    "explain", "explain", "explain", "explain", "explain", "explain", "explain", "explain",
    "practice", "practice", "practice", "practice", "practice", "practice", "practice",
    "check", "check", "check", "check", "check", "check",
    "support", "support", "support", "support", "support", "support", "support",
    "chat", "chat", "chat", "chat", "chat", "chat"
]
embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

X = embedder.encode(texts)
X_tr, X_te, y_tr, y_te = train_test_split(
    X, labels, test_size=0.2, stratify=labels, random_state=42
)

check_clf = LinearSVC().fit(X_tr, y_tr)
print(classification_report(y_te, check_clf.predict(X_te), zero_division=0))

# фінальна модель на всіх даних
clf = LinearSVC().fit(X, labels)
joblib.dump(clf, "ai-service/router_clf.joblib")