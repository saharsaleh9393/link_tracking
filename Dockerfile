# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
# A managed-cloud build can supply --secret id=proxy_ca,src=<combined CA bundle>.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.lock
RUN groupadd --gid 10001 tracker && useradd --uid 10001 --gid tracker --no-create-home tracker
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 deploy/runtime.py ./deploy/runtime.py
USER 10001:10001
EXPOSE 8000
CMD ["python", "deploy/runtime.py", "api"]
