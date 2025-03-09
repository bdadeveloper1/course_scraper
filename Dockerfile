# Use slim Python image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies including Git
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["chainlit", "run", "course_scraper.py", "-h", "0.0.0.0"]
