FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --no-dev

COPY artifacts/ artifacts/
COPY .dvc/config .dvc/config
COPY pipelines/data/*.dvc pipelines/data/
RUN uv run --no-sync dvc config --local core.no_scm true
ARG GIT_SHA=local
ENV GIT_SHA=$GIT_SHA

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "market.service.main:app", "--host", "0.0.0.0", "--port", "8000"]