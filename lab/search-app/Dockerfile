FROM python:3.13.7-alpine3.22
RUN --mount=type=secret,id=lab_ca if [ -s /run/secrets/lab_ca ]; then cat /run/secrets/lab_ca >> /etc/ssl/certs/ca-certificates.crt; fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt PIP_CERT=/etc/ssl/certs/ca-certificates.crt
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app.py rewrite_lookup.py telemetry.py variants.py search_filters.py index.html demo.py test_app.py test_demo.py test_filters.py test_pool.py test_rewrite_lookup.py ./
RUN python -m unittest -v
USER 1000
EXPOSE 8080
CMD ["python", "app.py"]
