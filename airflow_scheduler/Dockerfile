FROM --platform=linux/amd64 python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
# Updated to use openai==1.91.0 to fix proxies issue
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose port
EXPOSE 8080

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "main:app"] 