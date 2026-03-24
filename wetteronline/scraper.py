import asyncio
import re
import json
import time
import os
from datetime import datetime
from playwright.async_api import async_playwright
import paho.mqtt.client as mqtt

# Konfiguration
MQTT_HOST = "172.30.32.1"
LOCATION = os.getenv("LOCATION", "grafing")
# WICHTIG: Hier muss der Slash zwischen .de und /wetter/ stehen!
URL = f"https://www.wetteronline.de{LOCATION}"

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def send_discovery(h_id, h_name):
    # Discovery für Temperatur & Zustand
    base_topic = f"homeassistant/sensor/wo_{h_id}"
    client.publish(f"{base_topic}_temp/config", json.dumps({
        "name": f"WO Grafing {h_name} Temp",
        "state_topic": f"wetteronline/hourly/{h_id}/temp",
        "unit_of_measurement": "°C", "unique_id": f"wo_temp_{h_id}", "device_class": "temperature"
    }), retain=True)
    client.publish(f"{base_topic}_zustand/config", json.dumps({
        "name": f"WO Grafing {h_name} Zustand",
        "state_topic": f"wetteronline/hourly/{h_id}/zustand",
        "unique_id": f"wo_zustand_{h_id}", "icon": "mdi:weather-partly-cloudy"
    }), retain=True)

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        print(f"STARTE ABFRAGE: {URL}")
        try:
            await page.goto(URL, timeout=60000, wait_until="networkidle")
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(5)
            content = await page.content()

            # Extraktion von Temp und Wetter-Text (z.B. Sonnig)
            temps = re.findall(r'"temperature":"(\d+)°"', content)
            zustand = re.findall(r'"iconText":"([^"]+)"', content)

            if temps:
                client.connect(MQTT_HOST, 1883, 60)
                start_hour = datetime.now().hour
                for i in range(min(len(temps), len(zustand), 16)):
                    h_name = f"{(start_hour + i) % 24:02d}:00"
                    h_id = f"{(start_hour + i) % 24:02d}00"
                    send_discovery(h_id, h_name)
                    client.publish(f"wetteronline/hourly/{h_id}/temp", temps[i], retain=True)
                    client.publish(f"wetteronline/hourly/{h_id}/zustand", zustand[i], retain=True)
                    print(f"Update {h_name}: {temps[i]}°C, {zustand[i]}")
                client.disconnect()
            else:
                print("Keine Daten gefunden - Prüfe URL oder Selektoren.")
        except Exception as e:
            print(f"FEHLER: {e}")
        await browser.close()

if __name__ == "__main__":
    while True:
        asyncio.run(scrape())
        time.sleep(1800)
