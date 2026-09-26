FROM python:3.13.7-alpine3.22
WORKDIR /app
COPY app.py test_app.py ./
RUN python -m unittest -v
USER 1000
EXPOSE 8080
CMD ["python", "app.py"]
