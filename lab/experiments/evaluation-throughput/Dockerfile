FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844
WORKDIR /app
COPY lab/search-app/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock httpx==0.28.1
COPY lab/search-app/*.py /app/
COPY lab/search-app/index.html /app/
COPY lab/experiments/evaluation-throughput/*.py /experiment/
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 1000
CMD ["python", "/experiment/server.py"]
