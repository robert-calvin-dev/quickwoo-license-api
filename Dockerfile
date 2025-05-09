# Use official lightweight Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Expose port
EXPOSE 8000

# Start FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

