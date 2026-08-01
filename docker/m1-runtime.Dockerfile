FROM python:3.10-slim

WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY mlops/requirements/runtime.lock /tmp/runtime.lock
RUN pip install --no-cache-dir -r /tmp/runtime.lock

# The legacy project is copied only to validate its frozen M0 oracle.
COPY legacy-deployment /code
