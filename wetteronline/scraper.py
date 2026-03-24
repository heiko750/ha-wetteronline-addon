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
        browser = await p.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
        # Wir setzen ein riesiges Fenster, damit die Tabelle Platz hat
        context = await browser.new_context(viewport={"width": 1280, "height": 3000})
        
        # Cookie setzen (Zustimmung simulieren)
        await context.add_cookies([{"name": "euconsent-v2", "value": "CP-X", "domain": ".wetteronline.de", "path": "/"}])
        
        page = await context.new_page()
        print(f"STARTE ABFRAGE: {URL}")
        
        try:
            await page.goto(URL, timeout=60000, wait_until="domcontentloaded")
            # Wir geben der Seite 15 Sekunden Zeit zum Rendern
            await asyncio.sleep(15) 
            
            # Wir extrahieren die Daten per JavaScript direkt aus dem DOM
            data = await page.evaluate("""
                () => {
                    const results = [];
                    // Suche alle Stunden-Blöcke
                    const blocks = document.querySelectorAll('wo-forecast-hour, .forecast-hour, [class*="forecast-hour"]');
                    blocks.forEach(b => {
                        const h = b.innerText.match(/(\d{2}:00)/);
                        const t = b.innerText.match(/(\-?\d+)°/);
                        if (h && t) {
                            results.push({hour: h[1], temp: t[1]});
                        }
                    });
                    return results;
                }
            """)

            if data:
                print(f"ERFOLG: {len(data)} Paare direkt extrahiert!")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()
                
                seen_hours = set()
                for entry in data:
                    h_name = entry['hour']
                    t_val = entry['temp']
                    if h_name not in seen_hours and len(seen_hours) < 24:
                        h_id = h_name.replace(":", "")
                        send_discovery(h_id, h_name)
                        client.publish(f"wetteronline/hourly/{h_id}/temp", t_val, retain=True)
                        print(f"Gelesen -> {h_name}: {t_val}°C")
                        seen_hours.add(h_name)
                
                time.sleep(2)
                client.loop_stop()
                client.disconnect()
            else:
                print("Keine Daten gefunden. Erstelle Screenshot zur Analyse...")
                await page.screenshot(path="/usr/src/app/debug.png")

        except Exception as e:
            print(f"FEHLER: {e}")
        await browser.close()


if __name__ == "__main__":
    while True:
        asyncio.run(scrape())
        print("Warte 30 Minuten...")
        time.sleep(1800)
