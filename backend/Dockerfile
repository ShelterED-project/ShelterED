FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

# Real client IP behind Nginx (rate limiting keys on it): uvicorn trusts X-Forwarded-For only
# from FORWARDED_ALLOW_IPS (comma-separated IPs/networks). The default trusts nobody but
# localhost; set it to the Nginx container IP or its Docker network subnet in compose.
# Never "*" while the API port is reachable bypassing Nginx: clients could spoof their IP.
ENV FORWARDED_ALLOW_IPS=127.0.0.1,::1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
