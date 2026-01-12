FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Run with uvicorn - Railway sets PORT dynamically
# Use shell form for proper environment variable expansion
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
