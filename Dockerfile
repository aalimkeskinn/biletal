FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy project files
COPY . .

# Expose port and start Gunicorn (Render binds to $PORT)
CMD gunicorn app:app --bind 0.0.0.0:$PORT
