FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY data ./data
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" API_HOST=0.0.0.0 API_PORT=8000
EXPOSE 8000
CMD ["python", "-m", "voice_agent.api"]
