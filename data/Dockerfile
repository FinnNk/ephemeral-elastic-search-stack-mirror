FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_SYSTEM_CERTS=true

RUN uv pip install --system --no-cache azure-storage-blob==12.27.0 azure-identity==1.25.3

WORKDIR /app/data
COPY data/ /app/data/
COPY contracts/job_event.py /app/data/job_event.py
USER 10001:10001
CMD ["python", "job_entry.py"]
