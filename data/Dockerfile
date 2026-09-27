FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844

RUN pip install --no-cache-dir azure-storage-blob==12.27.0 azure-identity==1.25.3

WORKDIR /app/data
COPY data/ /app/data/
USER 10001:10001
CMD ["python", "job_entry.py"]
