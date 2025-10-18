# BotPanel — Telegram-driven Lab Control

> ⚠️ **IMPORTANT (Read before using)**
> **BotPanel** is an educational / lab tool. Use **only** on machines you own or where you have explicit, written permission to test. The authors and maintainers are **not responsible** for misuse, illegal activity, damages, or any consequences of using this software. By using this project you agree to follow all applicable laws and get permission before testing systems you do not own.

---

## What is BotPanel?

BotPanel is a small lab framework that demonstrates controlling a test agent over TCP using a Telegram bot (button-driven UI). It provides a whitelist of safe-ish actions for testing in a controlled environment and a screenshot feature that returns a base64 PNG in the ACK.

### Files in this repo

* `victim.py` — agent that runs on the target (lab) machine. Responds to whitelisted TCP JSON commands, including `screenshot`. **Run only on machines you own.**
* `botpanel_bot.py` — async Telegram controller (button-only UI using `python-telegram-bot` v20+). Stores per-chat target IP, probes the target, sends commands, and receives screenshots.
* `attacker_bot.py` — older/alternate bot UI (if present).
* `README.md` — this file.
* `.gitignore` — recommended ignore rules (see below).

---

## Legal & Safety Disclaimer

This project is provided **for educational, research, and authorized red-team / lab use only**. Do **NOT** use BotPanel to access, control, monitor, or disrupt machines that you do not own or do not have explicit permission to test. Misuse of these tools may be illegal and unethical.

The repository authors, contributors, and maintainers are **not liable** for any damage, data loss, legal claims, or other consequences arising from the use or misuse of this software. If you are unsure about the legality or ethics of using this tool in your environment, stop now and seek permission or legal advice.

---

## Quick demo (how it works)

1. Run `victim.py` on a lab machine (the *target*). It listens on a TCP port (default `9999`) and accepts JSON commands from the bot.
2. Run `botpanel_bot.py` (the Telegram bot). Use the buttons to:

   * **Set Target** — paste the target IP once; the bot will probe the target and store it per chat.
   * Use action buttons (e.g., `Screenshot`, `Crazy Brightness`, `Flash Screen`, `LOL`, `CLI Hack`, `Stop All`, `Shutdown`).
3. When `screenshot` is requested, the victim captures the screen, encodes PNG in base64, and returns it in the ACK. The bot decodes and posts the image to your Telegram chat.

---

## Features

* Button-driven Telegram UI (no command typing except for the target IP paste).
* Per-chat stored target IP.
* Probe/ACK when setting a target (verifies reachability and token).
* `screenshot` action: victim captures screen and returns base64 PNG in ACK (bot sends image to chat).
* Whitelisted commands only — built for lab/educational use.

---

## Requirements / Dependencies

### Python

* Python 3.8+ (use a virtualenv)

Install required packages:

```bash
pip install python-telegram-bot mss pillow
```

Optional (Windows-specific / extra features):

* `pywin32` (screen/window ops)
* `pyautogui` (keyboard/mouse automation)
* `screen_brightness_control` (brightness changes)

---

## Environment variables

**victim.py** uses:

* `TCP_PORT` (default `9999`)
* `TG_SECRET` (shared secret token)
* `ALLOW_SHUTDOWN` (`1` to allow shutdown — disabled by default)

**botpanel_bot.py** uses:

* `TG_BOT_TOKEN` — your Telegram bot token
* `TG_SECRET` — shared secret token that must match `victim.py`
* `TCP_PORT` — port to connect to on target (default `9999`)

Set env vars example (Linux / macOS):

```bash
export TG_BOT_TOKEN="123456:ABC-DEF...yourtoken..."
export TG_SECRET="your_shared_secret_here"
export TCP_PORT=9999
```

---

## How to run

1. Start the victim (on the machine you control):

```bash
# optionally install dependencies in a venv
python3 victim.py
```

The victim listens on `0.0.0.0:9999` by default. Change with the `TCP_PORT` env var.

> **Safety:** `ALLOW_SHUTDOWN=1` will allow remote shutdown; keep disabled unless you explicitly want that behavior.

2. Start the bot (controller):

```bash
python3 botpanel_bot.py
```

Interact with the bot in Telegram. Use the **Set Target** button, paste the target IP when prompted, then use the action buttons. The bot will probe the target and show ACKs or errors.

---

## Network protocol (overview)

Controller -> Victim: newline-terminated JSON

```json
{"token":"<shared token>", "id":"<uuid>", "cmd":"screenshot", "args":{}}
```

Victim -> Controller (ACK): newline-terminated JSON

```json
{"id":"<uuid>", "status":"ok", "msg":"screenshot", "img_b64":"<base64_png_here>"}
```

This repo uses a simple synchronous custom protocol over plain TCP for lab experiments only. It is **not** secure for production or internet-facing usage.

---

## Security notes

* Protocol traffic is plain TCP/JSON and not encrypted. Use only on isolated lab networks or over a VPN/tunneled secure channel when necessary.
* Keep `TG_SECRET` secret and random. If the secret leaks, rotate it immediately.
* Do not expose the victim port (default `9999`) to the public internet.
* For real red-team or production remote administration, use secure, authenticated, encrypted channels (SSH, TLS, mTLS, etc.).

---



## Troubleshooting

* If screenshot fails: ensure `mss` and `Pillow` are installed on the victim (`pip install mss pillow`). `mss` is preferred for cross-platform screenshots.
* If victim returns very large images: increase `MAX_MESSAGE_SIZE` in `victim.py` (careful) or enable downscaling with Pillow.
* If bot cannot reach victim: ensure firewall allows the port and both hosts are on the same network or route is allowed.

---

## Ethical use & contribution

If you find bugs or want to contribute safer workflows (e.g., HTTPS pull for image transfer, authenticated TLS, or persistent target store), open a PR and include clear safety and legal guidance in any changes.

---


