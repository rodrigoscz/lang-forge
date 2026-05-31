FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Astro build
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g pnpm

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy frontend and build Astro
COPY frontend/ ./frontend/
WORKDIR /app/frontend
RUN pnpm install && pnpm build
WORKDIR /app

# Copy application code
COPY backend/ ./backend/
COPY experiments/ ./experiments/
COPY data/ ./data/

# Create outputs directory
RUN mkdir -p outputs frontend/dist/_astro

# Set environment variables
ENV PYTHONPATH=/app:/app/backend
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
