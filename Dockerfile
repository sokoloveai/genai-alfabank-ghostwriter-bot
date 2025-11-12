FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --frozen

COPY src ./src
COPY main.py ./main.py
COPY config.py ./config.py

CMD ["uv", "run", "python", "main.py"]
