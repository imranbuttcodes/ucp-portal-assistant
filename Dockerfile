FROM python:3.10-slim

WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser and its system dependencies
RUN playwright install --with-deps chromium

# Copy the rest of the application code
COPY . .

# Ensure Python prints directly to the console (useful for Docker logs)
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "uni_agent_ntfy.py"]
