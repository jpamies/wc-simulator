FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/raw/players/ data/raw/players/
COPY data/tournament/ data/tournament/

RUN mkdir -p data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
