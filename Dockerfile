# Runs laya-serve on Linux. Use this on Windows when native torch DLLs are blocked
# (for example by Smart App Control, WinError 4551). Start with: docker compose up -d
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ scripts/
COPY data/schema/ data/schema/

# Inside the container the server must bind 0.0.0.0 to be reachable; docker-compose.yml
# publishes the port on 127.0.0.1 only, which is what keeps it local.
ENV LAYA_HOST=0.0.0.0 \
    LAYA_IN_CONTAINER=1 \
    LAYA_DEVICE=cpu \
    LAYA_MODELS=multilingual \
    LAYA_DEFAULT_MODEL=multilingual \
    LAYA_MAX_LOADED=1 \
    HF_HUB_CACHE=/cache

EXPOSE 8000
CMD ["python", "scripts/serve.py"]
