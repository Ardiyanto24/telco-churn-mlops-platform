FROM telco-churn-m6-runtime:local

COPY mlops/requirements/m7-runtime.lock /tmp/m7-runtime.lock
RUN pip install --no-cache-dir -r /tmp/m7-runtime.lock

# The M7 record supplies the authoritative Git revision. The slim runtime does
# not include Git, so suppress MLflow's redundant GitPython availability warning.
ENV GIT_PYTHON_REFRESH=quiet

WORKDIR /workspace
