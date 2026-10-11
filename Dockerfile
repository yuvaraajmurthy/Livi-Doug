FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY config ./config
COPY db ./db
COPY seed ./seed
COPY ingest ./ingest
COPY scripts ./scripts
COPY fixtures ./fixtures
COPY contract ./contract
COPY handoff/data/out ./handoff/data/out
COPY handoff/kb ./handoff/kb
RUN useradd -m -u 10001 compass && chown -R compass /srv
USER compass
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
