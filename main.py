import os
import pandas as pd
import re
import asyncio
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# ---------------- CONFIG ----------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WASENDER_API_URL = os.getenv("WASENDER_API_URL", "https://wasenderapi.com/api/send-message")
WASENDER_API_KEY = os.getenv("WASENDER_API_KEY", "YOUR_WASENDER_API_KEY")
SAVE_PATH = "loan_data.xlsx"
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "https://veritasfin.in/paynow/")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------- HELPERS ----------------
def clean_mobile(mobile):
    try:
        s = re.sub(r"\D", "", str(mobile))
        if s.startswith("91") and len(s) == 12:
            s = s[-10:]
        if len(s) == 10 and s[0] in "6789":
            return s
        return None
    except:
        return None

def to_float(x):
    try:
        if pd.isna(x):
            return 0.0
        return float(str(x).replace(",", "").strip())
    except:
        return 0.0

def build_msg(name, loan_no, advance, edi, overdue, payable, link):
    return (
        f"👋 ప్రియమైన {name} గారు,\n"
        f"Veritas Finance Limited నుండి మేము మాట్లాడుతున్నాం.\n\n"
        f"💳 లోన్ నంబర్: {loan_no}\n"
        f"💰 అడ్వాన్స్‌ మొత్తం = ₹{advance}\n"
        f"📌 ఈడీ మొత్తం = ₹{edi}\n"
        f"🔴 ఓవర్‌డ్యూ = ₹{overdue}\n"
        f"✅ చెల్లించవలసిన మొత్తం = ₹{payable}\n\n"
        f"దయచేసి వెంటనే చెల్లించండి.\n"
        f"🔗 చెల్లించడానికి లింక్: {link}{loan_no}"
    )

def send_whatsapp(phone, message):
    mobile = clean_mobile(phone)
    if not mobile:
        logging.warning(f"Invalid mobile: {phone}")
        return False
    payload = {"to": f"+91{mobile}", "text": message}
    headers = {"Authorization": f"Bearer {WASENDER_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(WASENDER_API_URL, json=payload, headers=headers)
        logging.info(f"Sent to {mobile}: {resp.status_code} | {resp.text}")
        return resp.status_code == 200
    except Exception as e:
        logging.error(f"Error sending to {mobile}: {e}")
        return False

# ---------------- EXCEL PROCESS ----------------
def process_excel(file_path):
    df = pd.read_excel(file_path, header=0)
    # Clean column names to remove non-breaking spaces
    df.columns = [c.replace("\xa0", " ").strip() for c in df.columns]
    for _, row in df.iterrows():
        loan_no = row.get("LOAN A/C NO")
        name = row.get("CUSTOMER NAME", "Customer")
        phone = row.get("MOBILE NO")
        edi = to_float(row.get("EDI AMOUNT"))
        overdue = to_float(row.get("OVER DUE"))
        advance = to_float(row.get("ADVANCE"))
        payable = edi + overdue - advance

        if payable <= 0:
            continue

        msg = build_msg(name, loan_no, advance, edi, overdue, payable, PAYMENT_LINK)
        send_whatsapp(phone, msg)
        asyncio.sleep(1)

# ---------------- TELEGRAM HANDLERS ----------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document and document.file_name.endswith(('.xlsx', '.xls')):
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive(SAVE_PATH)
        await update.message.reply_text("📂 ఫైల్ అందింది. సందేశాలు పంపుతున్నాం...")
        process_excel(SAVE_PATH)
        await update.message.reply_text("✅ అన్ని మెసేజ్లు పంపబడినవి.")
    else:
        await update.message.reply_text("❌ దయచేసి Excel ఫైల్ (.xlsx) పంపండి.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📂 Excel ఫైల్ పంపండి", callback_data="upload"),
        InlineKeyboardButton("ℹ️ బోట్ గురించి", callback_data="about")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "నేను మీ WhatsApp రిమైండర్ బోట్ ని. క్రింద ఎంపికలతో కొనసాగించండి:",
        reply_markup=reply_markup
    )

# ---------------- RUN BOT ----------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    logging.info("🤖 Telegram WhatsApp Bot Running...")
    app.run_polling()
