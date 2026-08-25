FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Install directly into the system site-packages instead of a project .venv,
# so `gunicorn` is on PATH without needing `uv run`.
ENV UV_PROJECT_ENVIRONMENT=/usr/local

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip uv

WORKDIR /app

# Copy only what `uv sync` needs first (pyproject/uv.lock, plus the local
# `mediaupload` package they reference as a path dependency) so this layer
# stays cached across unrelated code changes.
COPY pyproject.toml uv.lock /app/
COPY packages/ /app/packages/

RUN uv sync --frozen --no-install-project && \
    uv pip install --no-cache gunicorn

COPY . /app/

RUN mkdir -p /app/media

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]