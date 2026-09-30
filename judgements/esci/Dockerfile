FROM python:3.12-slim
WORKDIR /app
COPY judgements/esci/requirements.lock /app/esci-requirements.txt
RUN pip install --no-cache-dir -r /app/esci-requirements.txt
COPY judgements/predictor.py judgements/telemetry.py judgements/fetch_model.py /app/
COPY judgements/esci/__init__.py judgements/esci/contract.py judgements/esci/engine.py \
    judgements/esci/model.py judgements/esci/release.py /app/esci/
COPY judgements/esci/serve.py /app/serve_esci.py
RUN useradd --uid 10001 --create-home judge && chown -R judge:judge /app
USER 10001
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
ENTRYPOINT ["python"]
CMD ["/app/serve_esci.py"]
