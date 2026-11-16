FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5003

# Scorecard scanning calls a vision LLM on ANOTHER box (OpenAI-compatible
# API). The app container itself stays tiny and runs fine on a 1 GB NAS.
# Point it at your server with OCR_LLM_URL at deploy time, or in the app
# under Settings -> Scan LLM. Not baked in here: keep hostnames out of git.
ENV PORT=5003 \
    DATA_PATH=/data \
    APP_NAME=Galf \
    OCR_LLM_MODEL=fast

CMD ["sh", "-c", "python app.py"]
