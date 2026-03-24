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
MQTT_USER = os.getenv("MQTT_USER", "mqtt-user")
MQTT_PASS = os.getenv("MQTT_PASSWORD")
LOCATION = os.getenv("LOCATION", "grafing")
URL = f"https://www.wetteronline.de/wetter/{LOCATION.strip('/')}"

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def send_discovery(h_id, h_name):
    """Erstellt die Sensoren automatisch in Home Assistant"""
    topic = f"homeassistant/sensor/wo_{h_id}/config"
    payload = {
        "name": f"WO {h_name}",
        "state_topic": f"wetteronline/hourly/{h_id}/temp",
        "unit_of_measurement": "°C",
        "unique_id": f"wo_t_{h_id}",
        "device_class": "temperature",
        "state_class": "measurement"
    }
    client.publish(topic, json.dumps(payload), retain=True)

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", 
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = await browser.new_page()
        print(f"STARTE ABFRAGE: {URL}")

        try:
            await page.goto(URL, timeout=60000, wait_until="domcontentloaded")
            print("Seite geladen, simuliere Scrollen...")
            
            # Wir scrollen 2000 Pixel nach unten, um das Nachladen zu triggern
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(8) # Zeit zum Rendern geben
            
            content = await page.content()
            
            # Unser robuster Regex fuer Uhrzeit -> Zahl zwischen > <
            pairs = re.findall(r'(\d{2}:00).*?>\s*(\-?\d+)\s*<', content, re.DOTALL)

            if pairs:
                print(f"ERFOLG: {len(pairs)} Paare im Rohtext gefunden!")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()
                
                seen_hours = set()
                for h_name, t_val in pairs:
                    if h_name not in seen_hours and len(seen_hours) < 24:
                        temp_int = int(t_val)
                        if -25 < temp_int < 45:
                            h_id = h_name.replace(":", "")
                            send_discovery(h_id, h_name)
                            client.publish(f"wetteronline/hourly/{h_id}/temp", t_val, retain=True)
                            print(f"Gelesen -> {h_name}: {t_val}°C")
                            seen_hours.add(h_name)
                
                client.loop_stop()
                client.disconnect()
            else:
                print("Keine Daten gefunden. Mache Screenshot...")
                await page.screenshot(path="/usr/src/app/debug.png")

        except Exception as e:
            print(f"FEHLER: {e}")
        
        await browser.close()

if __name__ == "__main__":
    while True:
        asyncio.run(scrape())
        print("Warte 30 Minuten bis zum nächsten Scan...")
        time.sleep(1800)
