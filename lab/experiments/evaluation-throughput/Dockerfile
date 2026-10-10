FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_SYSTEM_CERTS=true
WORKDIR /app
COPY lab/search-app/requirements.lock /tmp/requirements.lock
RUN uv pip install --system --no-cache -r /tmp/requirements.lock httpx==0.28.1
COPY lab/search-app/*.py /app/
COPY lab/search-app/index.html /app/
COPY lab/experiments/evaluation-throughput/*.py /experiment/
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 1000
CMD ["python", "/experiment/server.py"]
