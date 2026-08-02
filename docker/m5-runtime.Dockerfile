FROM telco-churn-m2-runtime:local

WORKDIR /workspace

COPY mlops/requirements/runtime.lock /tmp/runtime.lock
RUN pip install --no-cache-dir -r /tmp/runtime.lock
