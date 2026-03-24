import asyncio
import re
import json
import time
import os
from datetime import datetime
from playwright.async_api import async_playwright
import paho.mqtt.client as mqtt

# Konfiguration aus der Add-on UI
MQTT_HOST = "172.30.32.1"
MQTT_USER = os.getenv("MQTT_USER", "mqtt-user")
MQTT_PASS = os.getenv("MQTT_PASSWORD")
LOCATION = os.getenv("LOCATION", "grafing")

# URL sicher zusammenbauen
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
        print(f"STARTE PRÄZISIONS-ABFRAGE: {URL}")


        
        try:
            await page.goto(URL, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            content = await page.content()
            
            # Wir suchen Paare aus Uhrzeit und Temperatur
            # Muster: >21:00</wo-date-hour> ... class="temperature"> 5
            # Das (?:.*?) überspringt die dynamischen IDs (_ngcontent...) dazwischen
            pairs = re.findall(r'>(\d{2}:00)</wo-date-hour>.*?class="temperature"[^>]*>\s*(\-?\d+)', content, re.DOTALL)

            if len(pairs) >= 12:
                print(f"ERFOLG: {len(pairs)} stündliche Paare gefunden!")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()
                
                for h_name, t_val in pairs[:16]:
                    h_id = h_name.replace(":", "")
                    
                    # Discovery & State senden
                    send_discovery(h_id, h_name)
                    client.publish(f"wetteronline/hourly/{h_id}/temp", t_val, retain=True)
                    print(f"Gelesen -> {h_name}: {t_val}°C")
                
                time.sleep(2)
                client.loop_stop()
                client.disconnect()
            else:
                print(f"Muster nicht gefunden. Treffer: {len(pairs)}")
                # Kleiner Tipp: Falls 0 Treffer, schau mal ob im Log '21:00' ohne '>' davor steht


            # Suche nach Temperaturen im Bereich nach "Wetter aktuell"
            # Dein Fund: class="temperature"> 5
            # Muster: class="temperature"> gefolgt von der Zahl
            # Wir suchen: class="temperature"> gefolgt von (optionalem Leerzeichen) und (Zahl)
            temps = re.findall(r'class="temperature"[^>]*>\s*(\-?\d+)', relevant_content)

            if len(temps) >= 16:
                print(f"PRÄZISIONS-ERFOLG: {len(temps)} stündliche Werte gefunden.")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()
                
                # Wir ordnen die Werte ab der aktuellen Stunde zu
                start_hour = datetime.now().hour
                for i in range(16):
                    current_h = (start_hour + i) % 24
                    h_id = f"{current_h:02d}00"
                    h_name = f"{current_h:02d}:00"
                    t_val = temps[i]
                    
                    send_discovery(h_id, h_name)
                    client.publish(f"wetteronline/hourly/{h_id}/temp", t_val, retain=True)
                    print(f"Update: {h_name} -> {t_val}°C")
                
                time.sleep(2)
                client.loop_stop()
                client.disconnect()
            else:
                print(f"Zu wenig relevante Temperaturen gefunden ({len(temps)}).")
                
        except Exception as e:
            print(f"FEHLER: {e}")
        
        await browser.close()

if __name__ == "__main__":
    while True:
        asyncio.run(scrape())
        print("Warte 30 Minuten bis zum nächsten Scan...")
        time.sleep(1800)
