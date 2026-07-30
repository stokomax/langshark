# ── Builder stage ────────────────────────────────────────────────────────────
FROM python:3.14-slim AS builder

# Install uv for fast, reproducible dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy source and metadata first so uv can build the package
COPY src/ ./src/
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (no project yet, so uv sync won't try to build langshark)
RUN uv sync --frozen --no-dev --no-install-project

# Build wheel and install it properly (non-editable)
RUN uv build --wheel && uv pip install dist/*.whl

# Install textual-dev for the web UI entrypoint (textual serve)
RUN uv pip install textual-dev


# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.14-slim

# Non-root user for security
RUN groupadd -r langshark && useradd -r -g langshark langshark

WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy entrypoint script that dispatches between TUI and web modes
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER langshark

# textual serve listens on 8000 by default
EXPOSE 8000

# TUI mode:   docker run -it --rm langshark -c URL
# Web mode:   docker run -it --rm -p 8000:8000 langshark web "langshark.__main__:app -c URL"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["--help"]
