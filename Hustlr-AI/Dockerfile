# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code into the container
COPY . .

# Run the server (Uvicorn)
# We use 0.0.0.0 so it can be reached from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]