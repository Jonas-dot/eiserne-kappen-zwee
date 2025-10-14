#!/usr/bin/env python3
"""
Ticket-Drucker mit Raspberry Pi Tastensteuerung oder Tastatur-Testmodus
"""

import os
import platform
import subprocess
import time
from datetime import datetime

import cv2
from pyzbar.pyzbar import decode
from PIL import Image, ImageDraw, ImageFont
import qrcode

# -------------------------
# Testmodus auf Mac/PC
TEST_MODE = True  # True = Keyboard-Test, False = Raspberry Pi GPIO

if not TEST_MODE:
    import RPi.GPIO as GPIO

# -------------------------
# Konfiguration

OUTPUT_DIR = "output"
OUTPUT_BASENAME = "ticket"

# QR-Code Positionierung auf A6
QR_SIZE = 180
A6_WIDTH = 1240
A6_HEIGHT = 1748
BASE_QR_POS = ((A6_WIDTH - QR_SIZE) // 2, (A6_HEIGHT - QR_SIZE) // 2)
QR_OFFSET_X = 115
QR_OFFSET_Y = 820
QR_INSERT_POS = (BASE_QR_POS[0] + QR_OFFSET_X, BASE_QR_POS[1] + QR_OFFSET_Y)

# Texte für Knöpfe 1-4
BUTTON_TEXTS = {
    1: "Waldseite",
    2: "Gegengerade",
    3: "Wuhleseite",
    4: "Haupttribüne",
}

# Font- und Textparameter
FONT_PATH = "fonts/Arial.ttf"

FONT_SIZE = 60  # Textgröße
TEXT_X_OFFSET = 80  # Verschiebung X
TEXT_Y_OFFSET = -630  # Verschiebung Y

if not TEST_MODE:
    BUTTON_PINS = {1: 5, 2: 6, 3: 13, 4: 19, 5: 26, 6: 21}

# -------------------------
# Hilfsfunktionen


def make_output_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_text_ticket(
    text, out_path, font_size=FONT_SIZE, x_offset=TEXT_X_OFFSET, y_offset=TEXT_Y_OFFSET
):
    """Erstellt ein reines Text-Ticket, 270° gedreht, ohne dass unten etwas abgeschnitten wird."""
    img = Image.new("RGB", (A6_WIDTH, A6_HEIGHT), (255, 255, 255))
    font = ImageFont.truetype(FONT_PATH, font_size)

    # Textgröße inkl. Descent ermitteln
    draw_dummy = ImageDraw.Draw(img)
    bbox = draw_dummy.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    ascent, descent = font.getmetrics()
    h_total = h + descent  # Gesamthöhe inklusive Descent

    # Textbild erstellen
    text_img = Image.new("RGBA", (w, h_total), (255, 255, 255, 0))
    draw_text = ImageDraw.Draw(text_img)
    draw_text.text((0, 0), text, font=font, fill=(0, 0, 0))

    # 270° drehen
    rotated_text = text_img.rotate(270, expand=True)

    # Position berechnen
    pos = (
        (A6_WIDTH - rotated_text.width) // 2 + x_offset,
        (A6_HEIGHT - rotated_text.height) // 2 + y_offset,
    )

    img.paste(rotated_text, pos, rotated_text)
    img.save(out_path)
    return out_path


def create_qr_text_ticket(
    qr_text,
    plain_text,
    out_path,
    font_size=FONT_SIZE,
    x_offset=TEXT_X_OFFSET,
    y_offset=TEXT_Y_OFFSET,
):
    """Erstellt ein Ticket mit QR-Code + Text"""
    img = Image.new("RGB", (A6_WIDTH, A6_HEIGHT), (255, 255, 255))

    # QR-Code
    qr_img = qrcode.make(qr_text).convert("RGB")
    qr_img = qr_img.resize((QR_SIZE, QR_SIZE))
    img.paste(qr_img, QR_INSERT_POS)

    # Text darunter
    font = ImageFont.truetype(FONT_PATH, font_size)
    draw_dummy = ImageDraw.Draw(img)
    bbox = draw_dummy.textbbox((0, 0), plain_text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    text_img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    draw_text = ImageDraw.Draw(text_img)
    draw_text.text((0, 0), plain_text, font=font, fill=(0, 0, 0))

    rotated_text = text_img.rotate(270, expand=True)
    pos = (
        (A6_WIDTH - rotated_text.width) // 2 + x_offset,
        QR_INSERT_POS[1] + QR_SIZE + 20 + y_offset,
    )
    img.paste(rotated_text, pos, rotated_text)

    img.save(out_path)
    return out_path


def send_to_printer(filepath):
    system = platform.system()
    if system in ("Linux", "Darwin"):
        try:
            subprocess.run(
                [
                    "lp",
                    "-d",
                    "Canon_TS5350i_series_2",
                    "-o",
                    "media=A6",
                    "-o",
                    "media-source=rear",
                    "-o",
                    "MediaType=photographic",
                    "-o",
                    "print-quality=3",
                    "-o",
                    "resolution=600dpi",
                    filepath,
                ],
                check=True,
            )
            print("Druckauftrag gesendet:", filepath)
        except Exception as e:
            print("Fehler beim Drucken:", e)
    elif system == "Windows":
        try:
            import os

            os.startfile(os.path.abspath(filepath), "print")
        except Exception as e:
            print("Fehler beim Drucken unter Windows:", e)


def scan_qr_code():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Kamera konnte nicht geöffnet werden.")
        return None
    print("QR-Code Kamera gestartet. Halte QR-Code vor die Kamera.")
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


def delete_file(filepath):
    try:
        os.remove(filepath)
        print("Datei gelöscht:", filepath)
    except Exception as e:
        print("Fehler beim Löschen der Datei:", e)


# -------------------------
# Hauptlogik


def main():
    make_output_dir(OUTPUT_DIR)
    selected_text = None

    if not TEST_MODE:
        GPIO.setmode(GPIO.BCM)
        for pin in BUTTON_PINS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    print(
        "Starte Ticket-Drucker (Testmodus)"
        if TEST_MODE
        else "Starte Ticket-Drucker (GPIO)"
    )

    try:
        while True:
            if TEST_MODE:
                key = input("Drücke 1-6 zum Testen (q=quit): ")
                if key == "q":
                    break
                if key in ["1", "2", "3", "4"]:
                    selected_text = BUTTON_TEXTS[int(key)]
                    print(f"Text ausgewählt: {selected_text}")
                elif key == "5":
                    if selected_text:
                        filename = os.path.join(
                            OUTPUT_DIR, f"{OUTPUT_BASENAME}_{timestamp()}.png"
                        )
                        create_text_ticket(selected_text, filename)
                        send_to_printer(filename)
                        print("Text-Ticket gedruckt.")
                    else:
                        print("Kein Text ausgewählt.")
                elif key == "6":
                    if selected_text:
                        qr_text = scan_qr_code()
                        if qr_text:
                            filename = os.path.join(
                                OUTPUT_DIR, f"{OUTPUT_BASENAME}_{timestamp()}.png"
                            )
                            create_qr_text_ticket(qr_text, selected_text, filename)
                            send_to_printer(filename)

                            print("QR+Text-Ticket gedruckt.")
                        else:
                            print("Kein QR-Code erkannt.")
                    else:
                        print("Kein Text ausgewählt.")
                delete_file(filename)  # Datei nach dem Druck löschen
            else:
                # GPIO-Logik Raspberry Pi hier implementieren
                pass

    except KeyboardInterrupt:
        print("Beendet.")
    finally:
        if not TEST_MODE:
            GPIO.cleanup()


if __name__ == "__main__":
    main()
