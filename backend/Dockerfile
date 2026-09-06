# Backend container for AI Trace Explorer
FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (better layer caching - only re-runs
# pip install when requirements.txt actually changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
