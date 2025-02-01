# Use a lightweight Python image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install Tkinter (python3-tk) and clean up to keep the image lean
RUN apt-get update && apt-get install -y python3-tk && rm -rf /var/lib/apt/lists/*

# Copy in the dependencies file and install Python packages
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Set the default command to run the scraper script
CMD ["python", "scrape.py"]