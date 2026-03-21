ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:latest
FROM $BUILD_FROM

COPY rootfs/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt || true
# new
# force rebuild
# force rebuild3
