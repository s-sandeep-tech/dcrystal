FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set PYTHONPATH to include current directory for package resolution
ENV PYTHONPATH=/app

CMD ["python", "run.py"]
