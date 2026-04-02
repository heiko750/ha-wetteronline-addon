import asyncio, re, json, time, os
from datetime import datetime
from playwright.async_api import async_playwright
import paho.mqtt.client as mqtt

# --- KONFIGURATION ---
MQTT_HOST = "core-mosquitto"
MQTT_USER = os.getenv("MQTT_USER", "mqtt-user")
MQTT_PASS = os.getenv("MQTT_PASSWORD")
LOCATION = os.getenv("LOCATION", "grafing")
URL = f"https://www.wetteronline.de/wetter/{LOCATION.strip('/')}"

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def send_discovery(h_id, h_name, sensor_type, unit, icon):
    topic = f"homeassistant/sensor/wo_{h_id}_{sensor_type}/config"
    payload = {
        "name": f"WO {h_name} {sensor_type.capitalize()}",
        "state_topic": f"wetteronline/hourly/{h_id}/{sensor_type}",
        "unique_id": f"wo_{sensor_type}_{h_id}",
        "icon": icon,
        "device_class": "temperature" if sensor_type == "temp" else None,
        "unit_of_measurement": unit if unit else None
    }
    client.publish(topic, json.dumps(payload), retain=True)

async def scrape():
    async with async_playwright() as p:
        # Tarnung: Wir geben uns als normaler Desktop-Browser aus
        browser = await p.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1000}
        )
        page = await context.new_page()
        
        print(f"STARTE SCAN: {URL}")
        try:
            # 1. Seite laden mit langer Wartezeit
            response = await page.goto(URL, timeout=60000, wait_until="load")
            print(f"Status Code: {response.status if response else 'Kein Response'}")
            
            # Warten, bis die Seite wirklich aufgebaut ist
            await asyncio.sleep(10)

            # Debug-Screenshot: Was sieht der Bot am Anfang?
            await page.screenshot(path="/usr/src/app/step1_start.png")

            # 2. Cookie-Banner mit Brute-Force wegschalten
            try:
                for text in ["Akzeptieren", "Zustimmen", "Alle akzeptieren", "OK"]:
                    btn = page.get_by_role("button", name=re.compile(text, re.IGNORECASE))
                    if await btn.count() > 0:
                        print(f"Klicke Cookie-Button: {text}")
                        await btn.first.click()
                        await asyncio.sleep(3)
                        break
            except: pass

            # 3. Pfeil finden (neue, sehr breite Suche)
            # Wir suchen nach dem Element, das den Text "nächste Stunden" oder ähnliches im Umfeld hat
            arrow = page.locator(".arrow-right, [class*='arrow-right'], .hourly-forecast-container >> i").first
            
            if await arrow.count() > 0:
                print("Pfeil gefunden. Starte Klicks...")
                for k in range(17):
                    try:
                        await arrow.click(force=True)
                        await asyncio.sleep(0.4)
                    except: break
                print("Klicks beendet.")
            else:
                print("HINWEIS: Kein Pfeil gefunden. Versuche Direktsuche im Quelltext.")

            # 4. Daten-Extraktion (verbessert)
            data = await page.evaluate("""
                () => {
                    const items = [];
                    // Suche nach allen Divs, die eine Uhrzeit (z.B. 14:00) enthalten
                    const divs = Array.from(document.querySelectorAll('div, span, wo-forecast-hour'));
                    divs.forEach(d => {
                        const text = d.innerText || "";
                        const hourMatch = text.match(/^([0-2][0-9]:00)$/);
                        if (hourMatch) {
                            const parent = d.closest('div[class*="hour"], wo-forecast-hour, .forecast-hour');
                            if (parent) {
                                const h = hourMatch[1];
                                const tMatch = parent.innerText.match(/(-?\\d+)°/);
                                if (tMatch && !items.find(i => i.hour === h)) {
                                    items.push({
                                        hour: h,
                                        temp: tMatch[1],
                                        condition: "Check Screenshot",
                                        wind: "Check Screenshot"
                                    });
                                }
                            }
                        }
                    });
                    return items;
                }
            """)

            if data:
                print(f"ERFOLG: {len(data)} Stunden gefunden.")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()

                for entry in data[:24]:
                    h_id = entry['hour'].replace(":", "")
                    send_discovery(h_id, entry['hour'], "temp", "°C", "mdi:thermometer")
                    client.publish(f"wetteronline/hourly/{h_id}/temp", entry['temp'], retain=True)
                
                print("Daten gesendet.")
                time.sleep(2)
                client.loop_stop(); client.disconnect()
            else:
                print("FEHLER: Keine Daten gefunden. Siehe Screenshot step2_final.png")
                await page.screenshot(path="/usr/src/app/step2_final.png")

        except Exception as e:
            print(f"FEHLER: {e}")
            
        await browser.close()

if __name__ == "__main__":
    while True:
        asyncio.run(scrape())
        print("Warte 30 Min...")
        time.sleep(1800)
