FROM python:3.11-slim
WORKDIR /app
COPY packages/sentinel-common /deps/sentinel-common
RUN pip install --no-cache-dir /deps/sentinel-common
COPY packages/sentinel-ai .
RUN pip install --no-cache-dir -e .
EXPOSE 5002
CMD ["uvicorn", "sentinel_ai.app:app", "--host", "0.0.0.0", "--port", "5002"]
