import os
import sqlite3
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ratebot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]        # مثلاً @my_channel یا -100123...
ADMIN_ID = int(os.environ["ADMIN_ID"])       # آیدی عددی تلگرام تو
KABUL = ZoneInfo("Asia/Kabul")

# ارز، نام نمایشی، واحد نمایش
CURRENCIES = [
    ("USD", "🇺🇸 دالر امریکا", 1),
    ("EUR", "🇪🇺 یورو", 1),
    ("GBP", "🇬🇧 پوند", 1),
    ("PKR", "🇵🇰 روپیه پاکستانی", 100),
    ("INR", "🇮🇳 روپیه هند", 100),
    ("IRT", "🇮🇷 تومان ایران", 100000),
]
MAX_CHANGE = 0.05  # اگر نرخ بیشتر از ۵٪ تغییر کرد، پست نمی‌شود

API = "https://api.frankfurter.dev/v2/rate/{cur}/AFN"


# ---------- دیتابیس ----------
def db():
    con = sqlite3.connect("rates.db")
    con.execute(
        "CREATE TABLE IF NOT EXISTS rates "
        "(day TEXT, slot TEXT, cur TEXT, rate REAL)"
    )
    return con


def last_rate(cur):
    row = db().execute(
        "SELECT rate FROM rates WHERE cur=? ORDER BY rowid DESC LIMIT 1", (cur,)
    ).fetchone()
    return row[0] if row else None


def save_rates(rates, slot):
    con = db()
    day = datetime.now(KABUL).strftime("%Y-%m-%d")
    con.executemany(
        "INSERT INTO rates VALUES (?,?,?,?)",
        [(day, slot, c, r) for c, r in rates.items()],
    )
    con.commit()


# ---------- گرفتن نرخ ----------
async def fetch_rates():
    rates = {}
    async with httpx.AsyncClient(timeout=20) as client:
        for cur, _, _ in CURRENCIES:
            try:
                r = await client.get(API.format(cur=cur), params={"providers": "DAB"})
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    data = data[0]
                rates[cur] = float(data["rate"])
            except Exception as e:
                log.warning("failed %s: %s", cur, e)
    return rates


def check_sanity(rates):
    problems = []
    if "USD" not in rates:
        problems.append("نرخ دالر گرفته نشد.")
    for cur, new in rates.items():
        old = last_rate(cur)
        if old and abs(new - old) / old > MAX_CHANGE:
            problems.append(f"{cur}: از {old:.4f} به {new:.4f} (تغییر زیاد)")
    return problems


def build_message(rates):
    now = datetime.now(KABUL).strftime("%Y-%m-%d  %H:%M")
    lines = ["💱 نرخ ارز | نرخ مرجع دافغانستان بانک", f"🕗 {now}", ""]
    for cur, name, unit in CURRENCIES:
        if cur not in rates:
            continue
        new = rates[cur] * unit
        old = last_rate(cur)
        arrow = ""
        if old:
            old *= unit
            arrow = " ▲" if new > old + 1e-9 else " ▼" if new < old - 1e-9 else " ▬"
        label = name if unit == 1 else f"{name} ({unit:,})"
        lines.append(f"{label}: {new:,.2f} ؋{arrow}")
    lines += ["", "ℹ️ این نرخ‌ها مرجع رسمی است و ممکن است با نرخ بازار آزاد فرق داشته باشد."]
    return "\n".join(lines)


# ---------- بررسی هوشمند و ارسال ----------
async def check_and_publish(context: ContextTypes.DEFAULT_TYPE):
    rates = await fetch_rates()
    if not rates:
        return

    # بررسی اینکه آیا نرخ نسبت به آخرین ذخیره در دیتابیس تغییر کرده است یا خیر
    changed = False
    for cur, new in rates.items():
        old = last_rate(cur)
        if old is None or abs(new - old) > 1e-9:
            changed = True
            break

    # اگر نرخ‌ها تغییر کرده بودند، پست کن
    if changed:
        slot = datetime.now(KABUL).strftime("%H:%M")
        problems = check_sanity(rates)
        if problems:
            await context.bot.send_message(
                ADMIN_ID, "⚠️ نرخ‌ها تغییر کرده اما در صحت‌سنجی مشکل دارد:\n" + "\n".join(problems)
            )
            return
        
        text = build_message(rates)
        await context.bot.send_message(CHANNEL_ID, text)
        save_rates(rates, slot)
        log.info("Rates updated and published to channel.")


async def publish_manual(context: ContextTypes.DEFAULT_TYPE, dry_run=False):
    rates = await fetch_rates()
    text = build_message(rates)
    if dry_run:
        await context.bot.send_message(ADMIN_ID, "پیش‌نمایش:\n\n" + text)
        return
    slot = datetime.now(KABUL).strftime("%H:%M")
    await context.bot.send_message(CHANNEL_ID, text)
    save_rates(rates, slot)


# ---------- دستورها (فقط برای ادمین) ----------
async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await publish_manual(context, dry_run=True)


async def postnow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await publish_manual(context)
    await update.message.reply_text("ارسال شد ✅")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("preview", preview))
    app.add_handler(CommandHandler("postnow", postnow))
    
    # بررسی هر ۲ ساعت یک‌بار (۷۲۰۰ ثانیه)
    app.job_queue.run_repeating(check_and_publish, interval=7200, first=10)
    
    log.info("bot started with 2-hour interval check")
    app.run_polling()


if __name__ == "__main__":
    main()
