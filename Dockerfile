# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your app code
COPY . .

# Expose the port Chainlit uses (default is 8000)
EXPOSE 8000

# Command to run your Chainlit app (replace "course_scraper.py" with your main script)
CMD ["chainlit", "run", "course_scraper.py", "--host", "0.0.0.0", "-h"]
