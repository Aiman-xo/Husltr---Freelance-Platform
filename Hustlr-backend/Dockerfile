# 1. Use a slim version of Python to keep the image size small
FROM python:3.10-slim

# 2. Prevent Python from writing .pyc files and ensure logs are sent to the terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Install system dependencies
# We need 'libpq-dev' and 'gcc' so 'psycopg2' (Postgres driver) can compile correctly
# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Install Python dependencies
# Copy requirements first to leverage Docker's cache (faster builds)
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of your project code into the container
COPY . /app/

# 7. Expose the port Django runs on
EXPOSE 8000

# 8. Command to start the server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]