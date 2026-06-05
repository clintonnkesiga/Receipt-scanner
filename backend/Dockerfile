FROM python:3.12-slim

# System dependencies:
#   tesseract-ocr  — OCR engine used by pytesseract
#   tesseract-ocr-eng — English language data pack
#   libgl1, libglib2.0-0 — required by opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying source so this layer is cached.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --reload watches for source changes (volume-mounted in docker-compose).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
