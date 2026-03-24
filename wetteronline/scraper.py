import asyncio
import re
import json
import time
import os
from datetime import datetime
from playwright.async_api import async_playwright
import paho.mqtt.client as mqtt

# --- KONFIGURATION ---
MQTT_HOST = "172.30.32.1"
MQTT_USER = os.getenv("MQTT_USER", "mqtt-user")
MQTT_PASS = os.getenv("MQTT_PASSWORD")
LOCATION = os.getenv("LOCATION", "grafing")

# Die URL muss hier definiert sein!
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
        # 1. Browser starten
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium", 
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        # 2. Kontext erstellen (Hier werden Cookies und Viewport gesetzt)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 3000}
        )
        
        # 3. Cookie setzen, um den Banner zu umgehen
        await context.add_cookies([{
            "name": "euconsent-v2",
            "value": "CP-X",
            "domain": ".wetteronline.de",
            "path": "/"
        }])
        
        # 4. Seite im Kontext öffnen
        page = await context.new_page()
        print(f"STARTE ABFRAGE: {URL}")
        
        try:
            # Seite laden (domcontentloaded reicht für Quelltext)
            await page.goto(URL, timeout=60000, wait_until="domcontentloaded")
            print("Quelltext geladen, starte Text-Analyse...")
            await asyncio.sleep(5) 
            
            content = await page.content()
            
            # Wir suchen Paare direkt im Text:
            # 1. Die Uhrzeit (z.B. 23:00)
            # 2. Alles dazwischen (dynamische IDs etc.)
            # 3. Die Zahl nach der Klasse 'temperature'
            # Muster: >23:00</wo-date-hour> ... class="temperature"> 5
            pairs = re.findall(r'>(\d{2}:00)</wo-date-hour>.*?class="temperature"[^>]*>\s*(\-?\d+)', content, re.DOTALL)

            if pairs:
                print(f"ERFOLG: {len(pairs)} stündliche Paare im Text gefunden!")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()
                
                seen_hours = set()
                for h_name, t_val in pairs:
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
                print("Muster im Quelltext nicht gefunden. Versuche radikale Suche...")
                # Plan B: Einfach alle Zahlen nach 'temperature' finden
                all_temps = re.findall(r'class="temperature"[^>]*>\s*(\-?\d+)', content)
                print(f"Fallback ergab {len(all_temps)} nackte Temperaturen.")

        except Exception as e:
            print(f"FEHLER: {e}")
            
        await browser.close()

if __name__ == "__main__":
    while True:
        asyncio.run(scrape())
        print("Warte 30 Minuten bis zum nächsten Scan...")
        time.sleep(1800)
