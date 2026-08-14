#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# screenctl.py — Həm siçan, həm klaviatura ilə tam idarəetmə

import argparse
import re
import subprocess
import time
import threading
import numpy as np
import cv2

def adb_async(*args):
    """ADB əmrlərini arxa fonda çağırır ki, görüntü heç vaxt donmasın."""
    cmd = ["adb"] + list(args)
    # Debug üçün əmri terminala çap edirik (işləyəndən sonra silə bilərsiniz)
    # print(f"[*] ADB Executing: {' '.join(cmd)}") 
    def run():
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    threading.Thread(target=run, daemon=True).start()

def adb_sync(*args):
    return subprocess.run(["adb", *args], capture_output=True)

def get_real_size():
    """Telefonun fiziki ekran ölçüsünü tapır"""
    out = adb_sync("shell", "wm", "size").stdout.decode()
    m = re.search(r"(\d+)x(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else (1080, 2400)

def pick_size(real_w, real_h):
    """Video ölçüsünü 8-ə tam bölərək xətasız formaya salır"""
    w = min(real_w, 720)
    w = (w // 8) * 8
    h = int(w * real_h / real_w)
    h = (h // 8) * 8
    return max(w, 8), max(h, 8)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bitrate", default="4M")
    args = ap.parse_args()

    print("[*] Telefon axtarılır...")
    print(adb_sync("devices").stdout.decode())

    real_w, real_h = get_real_size()
    w, h = pick_size(real_w, real_h)
    scale_x, scale_y = real_w / w, real_h / h

    WINDOW = "Telefon - Canli Idare"
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)
    cv2.resizeWindow(WINDOW, 420, 930)

    # -------------------------------------------------------------
    # XƏTANIN HƏLLİ: OpenCV Qt pəncərəsi üçün ilkin kadr göstəririk
    # -------------------------------------------------------------
    blank_canvas = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.putText(blank_canvas, "Yuklenir...", (w // 4, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imshow(WINDOW, blank_canvas)
    cv2.waitKey(200)  # Pəncərənin sistemdə aktivləşməsini gözləyirik

    drag = None

    def on_mouse(event, x, y, flags, param):
        nonlocal drag
        # Telefon koordinatlarına çevirmək
        dx, dy = int(x * scale_x), int(y * scale_y)

        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"[*] Mouse Down: PC({x},{y}) -> Phone({dx},{dy})") # DEBUG ÇAPI
            drag = (dx, dy, time.time())

        elif event == cv2.EVENT_LBUTTONUP and drag:
            x0, y0, t0 = drag
            drag = None
            dt = int((time.time() - t0) * 1000)
            print(f"[*] Mouse Up: Phone({dx},{dy}) DT={dt}ms") # DEBUG ÇAPI

            # Klikləndi (Tap)
            if abs(dx - x0) < 20 and abs(dy - y0) < 20:
                adb_async("shell", "input", "tap", str(dx), str(dy))
            # Barmaqla sürüşdürüldü (Swipe)
            else:
                duration = str(max(80, min(800, dt)))
                adb_async("shell", "input", "swipe", str(x0), str(y0), str(dx), str(dy), duration)

        # Siçan təkəri (Həmişə şaquli sürüşdürür)
        elif event == cv2.EVENT_MOUSEWHEEL:
            center_x, center_y = real_w // 2, real_h // 2
            if flags > 0:  # Yuxarı
                adb_async("shell", "input", "swipe", str(center_x), str(center_y - 400), str(center_x), str(center_y + 400), "150")
            else:  # Aşağı
                adb_async("shell", "input", "swipe", str(center_x), str(center_y + 400), str(center_x), str(center_y - 400), "150")

    # Siçanı bağlayırıq
    cv2.setMouseCallback(WINDOW, on_mouse)

    try:
        while True:
            rec = subprocess.Popen(
                ["adb", "exec-out", "screenrecord",
                 "--output-format=h264", "--size", f"{w}x{h}",
                 "--bit-rate", args.bitrate, "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            ff = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-i", "pipe:0",
                 "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"],
                stdin=rec.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )

            frame_size = w * h * 3

            while True:
                raw = ff.stdout.read(frame_size)
                if not raw or len(raw) < frame_size:
                    break

                img = np.frombuffer(raw, np.uint8).reshape(h, w, 3)
                cv2.imshow(WINDOW, img)

                # Klaviaturanı oxumaq
                key_raw = cv2.waitKey(1)
                key = key_raw & 0xFF
                # Bəzi Linux sistemlərində xüsusi düymələr üçün key_raw lazımdır
                
                # Q və ya Esc: Çıxış
                if key in (27, ord('q')):
                    return

                # --- 🖮 5 YAŞLI UŞAQ ÜÇÜN SADƏ KLAVİATURA İDARƏETMƏSİ ---
                # H = HOME (Ana Ekran)
                elif key == ord('h'):
                    print("[*] Key: HOME")
                    adb_async("shell", "input", "keyevent", "3")
                # B = BACK (Geri)
                elif key == ord('b'):
                    print("[*] Key: BACK")
                    adb_async("shell", "input", "keyevent", "4")
                # R = RECENTS (Son Proqramlar)
                elif key == ord('r'):
                    print("[*] Key: RECENTS")
                    adb_async("shell", "input", "keyevent", "187")
                # U = UNLOCK (Ekranı Yandır)
                elif key == ord('u'):
                    print("[*] Key: UNLOCK")
                    adb_async("shell", "input", "keyevent", "224")

                # --- ⬅ SAĞA-SOLA SÜRÜŞDÜRMƏK (Ana Səhifə üçün) ---
                # Sol Arrow (⬅ düyməsi) -> Sağdan Sola Sürüşdür (Sola Get)
                elif key_raw == 81 or key == ord('a'): 
                    print("[*] Key: SWIPE LEFT")
                    adb_async("shell", "input", "swipe", "900", "1000", "100", "1000", "300")
                # Sağ Arrow (➡ düyməsi) -> Soldan Sağa Sürüşdür (Sağa Get)
                elif key_raw == 83 or key == ord('d'):
                    print("[*] Key: SWIPE RIGHT")
                    adb_async("shell", "input", "swipe", "100", "1000", "900", "1000", "300")

            rec.kill()
            ff.kill()
            time.sleep(1)

    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()