FROM python:3.11-slim

WORKDIR /app

# The consumer needs the app package for models and DB access
# We will mount the server directory into the consumer container
# or copy the necessary parts. For development, we'll use volumes.

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add the server directory to the PYTHONPATH so the app module can be found
ENV PYTHONPATH=/app:/app/server

CMD ["python", "main.py"]
