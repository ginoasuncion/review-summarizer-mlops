# Use an official Python runtime as the base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY telegram_bot.py .

# Set environment variables (will be overridden by Cloud Run)
ENV TELEGRAM_BOT_TOKEN=

# Run the bot
CMD ["python", "telegram_bot.py"]