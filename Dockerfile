FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5003

# Scorecard scanning calls a vision LLM on ANOTHER box on your LAN
# (Ollama native API recommended — supports keep_alive=0 so the model
# only occupies RAM there during a scan). The app container itself
# stays tiny and runs fine on a 1 GB NAS.
# Override OCR_LLM_URL with your helper box's LAN IP.
ENV PORT=5003 \
    SECRET_KEY=change-me-in-production \
    DATA_PATH=/data \
    APP_NAME=Galf \
    OCR_LLM_URL=http://host.docker.internal:11434/api/chat \
    OCR_LLM_MODEL=qwen2.5vl:3b \
    OCR_LLM_KEEP_ALIVE=0

CMD ["sh", "-c", "python app.py"]
