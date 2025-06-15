FROM python:3.10-slim AS runtime

# 1. Prevent python from writing .pyc files & set workdir
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Add libgomp1 for lightbm to avoid error when run on Jenkins 
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# 2. Copy dependency definition first for better cache‑hits
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the rest of your source & model artefact
COPY src/ ./src/

# 4. Create log directory and set permissions
RUN mkdir -p /var/log/container && \
    chmod 755 /var/log/container

# 5. Expose port 
EXPOSE 8000

# 6. Setup entrypoint and use the logging config
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "src/logging.conf"]