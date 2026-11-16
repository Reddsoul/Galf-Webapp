FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5003

# Scorecard scanning calls a vision LLM on ANOTHER box (OpenAI-compatible
# API). The app container itself stays tiny and runs fine on a 1 GB NAS.
# Configure the server in the app: Settings -> Scan LLM (URL, model,
# optional key; saved after Test Connection succeeds). No defaults.
ENV PORT=5003 \
    DATA_PATH=/data \
    APP_NAME=Galf

CMD ["sh", "-c", "python app.py"]
