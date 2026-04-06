FROM python:3.11-slim
WORKDIR /app
COPY packages/sentinel-common /deps/sentinel-common
RUN pip install --no-cache-dir /deps/sentinel-common
COPY packages/sentinel-core .
RUN pip install --no-cache-dir -e .
EXPOSE 8080
CMD ["uvicorn", "sentinel_core.app:app", "--host", "0.0.0.0", "--port", "8080"]
