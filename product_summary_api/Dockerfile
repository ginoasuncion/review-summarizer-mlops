FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app

USER app

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]

# Force rebuild 