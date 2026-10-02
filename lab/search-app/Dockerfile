FROM python:3.13.7-alpine3.22
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app.py telemetry.py variants.py search_filters.py index.html demo.py test_app.py test_demo.py test_filters.py test_pool.py ./
RUN python -m unittest -v
USER 1000
EXPOSE 8080
CMD ["python", "app.py"]
