FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_SYSTEM_CERTS=true
WORKDIR /app
RUN uv pip install --system --no-cache mlflow==3.16.1 psycopg2-binary==2.9.11 boto3==1.42.74 azure-storage-blob==12.27.0 azure-identity==1.25.3 opentelemetry-sdk==1.37.0 opentelemetry-exporter-otlp-proto-http==1.37.0
COPY judgements/*.py /app/
COPY judgements/esci/contract.py /app/esci/contract.py
COPY data/contracts.py /data/contracts.py
RUN useradd --uid 10001 --create-home judge && chown -R judge:judge /app
USER 10001
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python"]
CMD ["predictor.py"]
