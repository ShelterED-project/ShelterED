FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/appuser \
    HF_HUB_CACHE=/models

WORKDIR /srv

RUN useradd --system --uid 10001 --create-home appuser

# 1) torch CPU окремо, щоб не підтягнулася CUDA з PyPI
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 2) решта залежностей (у requirements.txt має не бути torch)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3) запікаємо модель в образ під час збірки (від root)
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')" \
    && chmod -R a+rX /models


ENV HF_HUB_OFFLINE=1

# код і артефакти класифікатора
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser router_clf.joblib ./router_clf.joblib

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]