FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5003

# Scorecard scanning calls a vision LLM on ANOTHER box (the Spark LLM
# server, OpenAI-compatible API over Tailscale). The app container itself
# stays tiny and runs fine on a 1 GB NAS. If the container can't resolve
# the *.ts.net name, override OCR_LLM_URL with the server's Tailscale IP.
ENV PORT=5003 \
    DATA_PATH=/data \
    APP_NAME=Galf \
    OCR_LLM_URL=http://localhost:4000/v1 \
    OCR_LLM_MODEL=fast

CMD ["sh", "-c", "python app.py"]
