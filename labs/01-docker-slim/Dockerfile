# Stage 1: install dependencies in a throwaway builder.
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: copy only the installed packages and the app into a clean slim base.
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app.py .
# Run as a non-root user: a small change that security reviewers look for.
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
# 0.0.0.0 so the port mapping (-p 8000:8000) can reach the app from outside the container.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
