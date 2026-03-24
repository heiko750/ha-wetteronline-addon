        try:
            await page.goto(URL, timeout=60000, wait_until="domcontentloaded")
            content = await page.content()
            
            # TRICK: Wir schneiden den Quelltext erst ab "Wetter aktuell" ab
            start_marker = "Wetter aktuell"
            if start_marker in content:
                # Wir nehmen nur den Teil NACH dem Marker
                relevant_content = content.split(start_marker)[1]
                print("Anker 'Wetter aktuell' gefunden. Suche startet...")
            else:
                relevant_content = content
                print("Anker nicht gefunden, nutze gesamten Quelltext.")

            # Jetzt suchen wir die Temperaturen im relevanten Bereich
            # Muster: class="temperature"> gefolgt von der Zahl
            temps = re.findall(r'class="temperature"[^>]*>\s*(\-?\d+)', relevant_content)

            if len(temps) >= 16:
                print(f"PRÄZISIONS-TREFFER: {len(temps)} stündliche Werte gefunden!")
                client.username_pw_set(MQTT_USER, MQTT_PASS)
                client.connect(MQTT_HOST, 1883, 60)
                client.loop_start()
                
                # Startzeitpunkt für die nächsten 16 Stunden
                start_hour = datetime.now().hour
                for i in range(16):
                    current_h = (start_hour + i) % 24
                    h_id = f"{current_h:02d}00"
                    h_name = f"{current_h:02d}:00"
                    t_val = temps[i]
                    
                    send_discovery(h_id, h_name)
                    client.publish(f"wetteronline/hourly/{h_id}/temp", t_val, retain=True)
                    print(f"Abgeglichen -> {h_name}: {t_val}°C")
