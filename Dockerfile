# Use a lightweight Python image
FROM python:3.12-slim

WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . .

# Expose the default Chainlit port
EXPOSE 8000

# Run Chainlit without opening a browser and bind to all interfaces
CMD ["chainlit", "run", "course_scraper.py", "--host", "0.0.0.0", "-h"]
