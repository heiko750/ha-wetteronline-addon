ARG BUILD_FROM=ghcr.io/hassio-addons/base-python:17.0.0
FROM ${BUILD_FROM}

# Install pip (Base-Python hat pip nicht vorinstalliert)
RUN apk add --no-cache py3-pip

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Copy your Python script
COPY scraper.py /app/scraper.py

CMD ["python3", "/app/scraper.py"]
