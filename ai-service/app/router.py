import asyncio
import os

import joblib
from sentence_transformers import SentenceTransformer

_BASE = os.path.dirname(os.path.abspath(__file__))
CLF_PATH = os.path.join(_BASE, "..", "router_clf.joblib")
EMBEDDER_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_embedder = None
_clf = None


def _load():
  global _embedder, _clf
  if _embedder is None:
    if not os.path.exists(CLF_PATH):
      raise FileNotFoundError(
          f"Файл класифікатора не знайдено: {CLF_PATH}. Спочатку натренуйте модель."
      )
    _embedder = SentenceTransformer(EMBEDDER_NAME)
    _clf = joblib.load(CLF_PATH)
  return _embedder, _clf


def _predict(message: str) -> str:
  embedder, clf = _load()
  embedding = embedder.encode([message])
  return str(clf.predict(embedding)[0])


async def route_intent(message: str, history: list | None = None) -> str:
  # encode блокує event loop, тому виконуємо в окремому потоці
  return await asyncio.to_thread(_predict, message)