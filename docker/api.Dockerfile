FROM python:3.10-slim AS builder

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements/runtime.lock /tmp/runtime.lock
RUN pip install --no-cache-dir -r /tmp/runtime.lock

WORKDIR /build
COPY src ./src

FROM python:3.10-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --create-home app

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    TELCO_CHURN_BUNDLE_DIR=/opt/telco-churn/model

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/src /app/src
USER app
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "telco_churn.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "30"]
