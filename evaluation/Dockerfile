FROM python:3.13.7-alpine3.22@sha256:9ba6d8cbebf0fb6546ae71f2a1c14f6ffd2fdab83af7fa5669734ef30ad48844
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_SYSTEM_CERTS=true

RUN apk add --no-cache libstdc++ && \
    apk add --no-cache --virtual .build-deps build-base && \
    uv pip install --system --no-cache numpy==2.5.3 scipy==1.18.1 ir_measures==0.4.3 pytrec_eval-terrier==0.5.10 azure-storage-blob==12.27.0 azure-identity==1.25.3 && \
    apk del .build-deps

WORKDIR /app
COPY evaluation/*.py /app/
COPY lab/search-app/search_filters.py /app/search_filters.py
COPY contracts/job_event.py /app/job_event.py
COPY evaluation/specs/ /app/specs/
USER 10001:10001
ENTRYPOINT ["python", "/app/offline.py"]
