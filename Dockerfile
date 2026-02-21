FROM python:3.12-slim

WORKDIR /app

ENV POETRY_NO_INTERACTION=1

ENV PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

COPY bot/pyproject.toml bot/poetry.lock /app/bot/
WORKDIR /app/bot
RUN poetry install --no-ansi --no-root --no-interaction

WORKDIR /app
COPY bot/ /app/bot/
COPY shared/ /app/shared/

CMD ["python", "bot/main.py"]