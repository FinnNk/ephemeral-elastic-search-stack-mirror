FROM python:3.13.7-slim@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689

RUN pip install --no-cache-dir papermill==2.7.0 ipykernel==6.30.1
WORKDIR /app
COPY lab/notebook/entry.py /app/entry.py
RUN mkdir /work && chown 10001:10001 /work
USER 10001:10001
ENTRYPOINT ["python", "/app/entry.py"]
