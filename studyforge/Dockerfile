FROM python:3.12-slim

# System dependencies:
#   tesseract-ocr + poppler-utils enable the optional OCR fallback for
#   image-heavy/scanned PDF pages (Phase 11 multimodal capability).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

RUN mkdir -p data/raw data/processed
ENV PYTHONUNBUFFERED=1
WORKDIR /srv/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
