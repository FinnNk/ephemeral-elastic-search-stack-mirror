FROM python:3.13.7-slim@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_SYSTEM_CERTS=true

RUN uv pip install --system --no-cache papermill==2.7.0 ipykernel==6.30.1
WORKDIR /app
COPY lab/notebook/entry.py /app/entry.py
RUN mkdir /work && chown 10001:10001 /work
USER 10001:10001
ENTRYPOINT ["python", "/app/entry.py"]
