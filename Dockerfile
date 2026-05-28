FROM python:3.12-slim

WORKDIR /app

# System dependencies for PDF/image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .

# Create directories
RUN mkdir -p uploads generated_reports

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
