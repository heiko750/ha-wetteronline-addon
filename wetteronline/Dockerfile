# Ersetze ARG und FROM durch diesen festen Wert:
FROM ghcr.io/home-assistant/aarch64-base-debian-python:3.12

# 1. System-Pakete für Debian installieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Python-Abhängigkeiten
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# 3. Playwright installieren
RUN pip3 install --no-cache-dir playwright

# 4. Umgebungsvariablen
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PLAYWRIGHT_CHROME_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /usr/src/app
COPY scraper.py .
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
