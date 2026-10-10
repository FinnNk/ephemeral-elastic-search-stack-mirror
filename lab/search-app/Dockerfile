FROM python:3.13.7-alpine3.22
COPY --from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1 UV_SYSTEM_CERTS=true
RUN --mount=type=secret,id=lab_ca if [ -s /run/secrets/lab_ca ]; then cat /run/secrets/lab_ca >> /etc/ssl/certs/ca-certificates.crt; fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt PIP_CERT=/etc/ssl/certs/ca-certificates.crt
WORKDIR /app
COPY requirements.lock ./
RUN uv pip sync --system --no-cache --require-hashes requirements.lock
COPY app.py rewrite_lookup.py telemetry.py variants.py search_filters.py index.html demo.py test_app.py test_demo.py test_filters.py test_pool.py test_rewrite_lookup.py ./
RUN python -m unittest -v
USER 1000
EXPOSE 8080
CMD ["python", "app.py"]
