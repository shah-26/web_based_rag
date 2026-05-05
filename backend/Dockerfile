# ---------- BASE IMAGE ----------
FROM python:3.11-slim as base

WORKDIR /app

# ---------- SYSTEM + PLAYWRIGHT (HEAVY LAYER) ----------
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install python deps first (cache-friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install playwright browsers (VERY HEAVY)
RUN playwright install chromium

# ---------- APP CODE (LIGHT LAYER) ----------
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]