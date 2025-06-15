# ────────────────────────────────────────────────────────────────
# Stage 1 : build runtime image
# ────────────────────────────────────────────────────────────────
FROM python:3.10-slim AS runtime

# 1. Prevent python from writing .pyc files & set workdir
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# ** NEW LINE: Install libgomp1 for LightGBM dependency **
# libgomp1 is a system library required by LightGBM for OpenMP support
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# 2. Copy dependency definition first for better cache‑hits
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the rest of your source & model artefact
COPY src/ ./src/
# COPY models/random_forest_model.pkl ./models/random_forest_model.pkl

# 4. Create log directory and set permissions
RUN mkdir -p /var/log/container && \
    chmod 755 /var/log/container

# 5. Expose port & declare non‑root user for k8s best practice
EXPOSE 8000

# —— FastAPI / Starlette / general ASGI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "src/logging.conf"]