# Use Python 3.9 as the base image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create required directories and files with proper permissions
RUN mkdir -p .files .chainlit && \
    touch chainlit.md && \
    chmod 777 .files && \
    chmod 777 .chainlit && \
    chmod 666 chainlit.md

# Expose the port that Chainlit will run on
EXPOSE 7860

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHAINLIT_HOST=0.0.0.0
ENV CHAINLIT_PORT=7860

# Command to run the application
CMD ["chainlit", "run", "main.py", "--host", "0.0.0.0", "--port", "7860"]
