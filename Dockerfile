FROM python:3.11-slim

# Install system dependencies: LibreOffice for Excel to PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    libreoffice-calc \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
