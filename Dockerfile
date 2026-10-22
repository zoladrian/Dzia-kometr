FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY landscope ./landscope
RUN pip install --no-cache-dir '.[test]'
COPY tests ./tests
COPY scripts ./scripts
RUN python scripts/fetch_assets.py
CMD ["python", "-m", "landscope", "serve", "--host", "0.0.0.0"]
