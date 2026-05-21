FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5003

ENV PORT=5003 \
    SECRET_KEY=change-me-in-production \
    DATA_PATH=/data \
    APP_NAME=Galf

CMD ["sh", "-c", "python app.py"]
