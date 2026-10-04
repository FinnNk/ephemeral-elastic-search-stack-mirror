FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir mlflow==3.16.1 psycopg2-binary==2.9.11 boto3==1.42.74 azure-storage-blob==12.27.0 azure-identity==1.25.3 opentelemetry-sdk==1.37.0 opentelemetry-exporter-otlp-proto-http==1.37.0
COPY judgements/*.py /app/
COPY judgements/esci/contract.py /app/esci/contract.py
COPY data/contracts.py /data/contracts.py
RUN useradd --uid 10001 --create-home judge && chown -R judge:judge /app
USER 10001
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python"]
CMD ["predictor.py"]
