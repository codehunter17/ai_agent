FROM python:3.11-slim

# Install Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 10000

# Run the app
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}