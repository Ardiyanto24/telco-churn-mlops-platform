FROM telco-churn-m5-runtime:local

# LightGBM's Linux wheel requires the GNU OpenMP runtime at import time.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
