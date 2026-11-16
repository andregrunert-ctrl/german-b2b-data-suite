FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy package metadata and source code before installing
COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Run as an unprivileged user
RUN useradd --create-home --shell /bin/sh mcpuser \
    && chown -R mcpuser:mcpuser /app
USER mcpuser

CMD ["python", "-m", "german_b2b_mcp.server"]
