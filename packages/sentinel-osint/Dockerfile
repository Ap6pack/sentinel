FROM python:3.11-slim
WORKDIR /app
COPY packages/sentinel-common /deps/sentinel-common
RUN pip install --no-cache-dir /deps/sentinel-common
COPY packages/sentinel-osint .
RUN pip install --no-cache-dir -e .
EXPOSE 5001
CMD ["uvicorn", "sentinel_osint.app:app", "--host", "0.0.0.0", "--port", "5001"]
