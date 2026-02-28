FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p /app/chroma_data

ENV DATABASE_URL=sqlite+aiosqlite:///./data/grug.db
ENV CHROMA_PERSIST_DIR=/app/chroma_data

VOLUME ["/app/data", "/app/chroma_data"]

CMD ["python", "main.py"]
