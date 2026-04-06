FROM python:3.11-slim
WORKDIR /app
COPY packages/sentinel-common /deps/sentinel-common
RUN pip install --no-cache-dir /deps/sentinel-common
COPY packages/sentinel-rf .
RUN pip install --no-cache-dir -e .
EXPOSE 5050
CMD ["python", "-m", "sentinel_rf.app"]
