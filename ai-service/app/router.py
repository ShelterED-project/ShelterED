import os
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "shelter_router.pkl")

_model_data = None


def get_model():
  global _model_data
  if _model_data is None:
    if not os.path.exists(MODEL_PATH):
      raise FileNotFoundError(
          f"Файл моделі не знайдено: {MODEL_PATH}. Спочатку запустіть навчання!"
      )
    _model_data = joblib.load(MODEL_PATH)
  return _model_data


async def route_intent(message: str, history: list = None) -> str:
  """Визначає інтент за повідомленням учня."""
  model_data = get_model()
  embedder = model_data["embedder"]
  classifier = model_data["classifier"]

  # Можеш за потреби враховувати history, або класифікувати лише поточне повідомлення message
  embedding = embedder.encode([message])
  intent = classifier.predict(embedding)[0]

  return intent