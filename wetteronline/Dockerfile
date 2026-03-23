ARG BUILD_FROM
FROM ${BUILD_FROM}

# Installiert System-Abhängigkeiten für Playwright & Chromium
RUN apk add --no-cache \
    python3-dev \
    gcc \
    musl-dev \
    playwright \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# WICHTIG: Playwright sagen, dass es den System-Chromium nutzen soll
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PLAYWRIGHT_CHROME_EXECUTABLE_PATH=/usr/bin/chromium-browser

WORKDIR /usr/src/app
COPY scraper.py .
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
