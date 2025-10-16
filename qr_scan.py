#!/usr/bin/env python3
"""
Ticket-Drucker mit Raspberry Pi (64-bit) und GPIO-Tastensteuerung.
Templates werden aus dem /templates-Ordner geladen.
Button 5: Template direkt drucken
Button 6: QR-Code scannen, einfügen, drucken
Testmodus: Tastatureingaben 1-6 simulieren Buttons
"""

import os
import platform
import subprocess
import time
from datetime import datetime
import logging

import cv2
from pyzbar.pyzbar import decode
from PIL import Image
import qrcode

# -------------------------
# KONFIGURATION

TEST_MODE = True  # True = Keyboard-Test, False = Raspberry Pi GPIO

TEMPLATE_DIR = "templates"
OUTPUT_DIR = "output"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "statistics.log")

PRINTER_NAME = "Canon_TS5350i_series_USB"

# Buttons (BCM-Nummern)
BUTTON_PINS = {1: 5, 2: 6, 3: 13, 4: 19, 5: 26, 6: 21}

# QR-Code Einstellungen
QR_SIZE = 180
QR_INSERT_POS = (1540, 255)  # Position des QR-Codes auf dem Ticket

# Template Y-Offset in Pixeln (verschiebt Template nach unten)
TEMPLATE_Y_OFFSET = 20  # z.B. 20 Pixel nach unten

if not TEST_MODE:
    import RPi.GPIO as GPIO

# -------------------------
# LOGGING


def init_logger():
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    print(f"Logging aktiviert → {LOG_FILE}")


def log_event(level, message):
    if level == "error":
        logging.error(message)
    else:
        logging.info(message)


# -------------------------
# Hilfsfunktionen


def make_output_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def scan_qr_code():
    """Startet Kamera und liest QR-Code ein"""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Kamera konnte nicht geöffnet werden.")
        log_event("error", "Kamera konnte nicht geöffnet werden.")
        return None

    print("QR-Code Scan gestartet – halte Code vor die Kamera (q zum Abbrechen).")
    qr_text = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        barcodes = decode(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        for b in barcodes:
            qr_text = b.data.decode("utf-8")
            cap.release()
            cv2.destroyAllWindows()
            print("QR-Code erkannt:", qr_text)
            return qr_text
        cv2.imshow("QR Scan (q zum Abbrechen)", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()
    return None


def overlay_qr_on_template(
    template_path, qr_text, out_path, y_offset=TEMPLATE_Y_OFFSET
):
    """Fügt QR-Code an vorgegebener Position in das Template ein und verschiebt Template Y"""
    img = Image.open(template_path).convert("RGB")

    # Template verschieben
    if y_offset != 0:
        width, height = img.size
        new_img = Image.new("RGB", (width, height + y_offset), (255, 255, 255))
        new_img.paste(img, (0, y_offset))
        img = new_img

    if qr_text:
        qr_img = qrcode.make(qr_text).convert("RGB")
        qr_img = qr_img.resize((QR_SIZE, QR_SIZE))
        img.paste(qr_img, QR_INSERT_POS)
    img.save(out_path)
    return out_path


def send_to_printer(filepath):
    """Schickt Datei an Drucker über CUPS (lp)"""
    system = platform.system()
    if system in ("Linux", "Darwin"):
        try:
            subprocess.run(
                [
                    "lp",
                    "-d",
                    PRINTER_NAME,
                    "-o",
                    "media=A6",
                    "-o",
                    "media-source=rear",
                    "-o",
                    "MediaType=plain",
                    "-o",
                    "print-quality=1",  # Draft / Low
                    "-o",
                    "resolution=300dpi",  # schneller
                    "-o",
                    "orientation-requested=4",  # Hochformat
                    filepath,
                ],
                check=True,
            )
            print("Druckauftrag gesendet:", filepath)
            return True
        except Exception as e:
            print("Fehler beim Drucken:", e)
            log_event("error", f"Druckfehler: {e}")
            return False
    elif system == "Windows":
        try:
            os.startfile(os.path.abspath(filepath), "print")
            return True
        except Exception as e:
            print("Fehler beim Drucken unter Windows:", e)
            log_event("error", f"Druckfehler (Windows): {e}")
            return False


def delete_file(filepath):
    """Löscht die Datei, falls vorhanden"""
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            print("Datei gelöscht:", filepath)
        except Exception as e:
            print("Fehler beim Löschen der Datei:", e)
            log_event("error", f"Fehler beim Löschen: {e}")


# -------------------------
# HAUPTLOGIK


def main():
    make_output_dir(OUTPUT_DIR)
    init_logger()

    if not TEST_MODE:
        GPIO.setmode(GPIO.BCM)
        for pin in BUTTON_PINS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    selected_template = None
    templates = {
        1: (
            "Waldseite",
            os.path.join(TEMPLATE_DIR, "ws_eintrittskarte_gladbach_waldseite.png"),
        ),
        2: (
            "Gegengerade",
            os.path.join(TEMPLATE_DIR, "ws_eintrittskarte_gladbach_gegengerade.png"),
        ),
        3: (
            "Wuhleseite",
            os.path.join(TEMPLATE_DIR, "ws_eintrittskarte_gladbach_wuhleseite.png"),
        ),
        4: (
            "Haupttribüne",
            os.path.join(TEMPLATE_DIR, "ws_eintrittskarte_gladbach_haupttribuene.png"),
        ),
    }

    mode_text = "Testmodus (Tastatur) aktiviert." if TEST_MODE else "GPIO-Modus"
    print(f"Ticket-Drucker gestartet. {mode_text}")
    print(
        "Tasten 1–4: Template wählen | Taste 5: Direktdruck | Taste 6: QR-Scan + Druck"
    )

    try:
        while True:
            filename = None
            if TEST_MODE:
                key = input("Drücke 1-6 (q=Beenden): ")
                if key == "q":
                    break
                if key in ["1", "2", "3", "4"]:
                    selected_template = templates[int(key)]
                    print(f"Template ausgewählt: {selected_template[0]}")
                elif key in ["5", "6"]:
                    if not selected_template:
                        print("Bitte zuerst Template wählen (1–4).")
                        continue

                    sector_name, template_path = selected_template
                    qr_mode = key == "6"
                    qr_text = scan_qr_code() if qr_mode else ""

                    filename = os.path.join(OUTPUT_DIR, f"ticket_{timestamp()}.png")
                    overlay_qr_on_template(
                        template_path, qr_text, filename, y_offset=TEMPLATE_Y_OFFSET
                    )

                    if send_to_printer(filename):
                        log_event(
                            "info",
                            f"Ticket gedruckt: Sektor={sector_name} | QR={qr_mode}",
                        )
                        delete_file(filename)
                    else:
                        log_event(
                            "error", f"Druckfehler: Sektor={sector_name} | QR={qr_mode}"
                        )
                else:
                    print("Ungültige Eingabe. 1–6 oder q zum Beenden.")
            else:
                # GPIO-Modus
                for num, pin in BUTTON_PINS.items():
                    if GPIO.input(pin) == GPIO.LOW:
                        time.sleep(0.2)
                        if num in [1, 2, 3, 4]:
                            selected_template = templates[num]
                            print(f"Template ausgewählt: {selected_template[0]}")
                        elif num in [5, 6] and selected_template:
                            sector_name, template_path = selected_template
                            qr_mode = num == 6
                            qr_text = scan_qr_code() if qr_mode else ""

                            filename = os.path.join(
                                OUTPUT_DIR, f"ticket_{timestamp()}.png"
                            )
                            overlay_qr_on_template(
                                template_path,
                                qr_text,
                                filename,
                                y_offset=TEMPLATE_Y_OFFSET,
                            )

                            if send_to_printer(filename):
                                log_event(
                                    "info",
                                    f"Ticket gedruckt: Sektor={sector_name} | QR={qr_mode}",
                                )
                                delete_file(filename)
                            else:
                                log_event(
                                    "error",
                                    f"Druckfehler: Sektor={sector_name} | QR={qr_mode}",
                                )
                        while GPIO.input(pin) == GPIO.LOW:
                            time.sleep(0.1)
            if not TEST_MODE:
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("Beendet.")
    finally:
        if not TEST_MODE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()
