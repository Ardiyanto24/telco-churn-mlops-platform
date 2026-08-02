FROM telco-churn-m8-runtime:local AS builder

WORKDIR /build
COPY src ./src

FROM telco-churn-m8-runtime:local AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --create-home app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    TELCO_CHURN_BUNDLE_DIR=/opt/telco-churn/model

COPY --from=builder /build/src /app/src
USER app
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "telco_churn.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "30"]
