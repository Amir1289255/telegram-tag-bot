
from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN = "9151851716:AAHF5Xb2AAkq_BHpwI4K5FtrYPPI7Ma2w1g"

DB_FILE = "db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_db()
active_tasks = {}

async def is_admin(update, context):
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, update.effective_user.id
        )
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط ادمین‌ها.")
        return
    chat_id = str(update.effective_chat.id)
    target_id = target_name = None
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        target_id = user.id
        target_name = user.first_name or user.username or str(user.id)
    elif context.args:
        arg = context.args[0].lstrip("@")
        target_id = f"@{arg}"
        target_name = arg
    else:
        await update.message.reply_text("`/id @user` یا ریپلای + `/id`", parse_mode="Markdown")
        return
    db.setdefault(chat_id, {})
    db[chat_id]["target_id"] = target_id
    db[chat_id]["target_name"] = target_name
    save_db(db)
    await update.message.reply_text(f"✅ ذخیره شد: `{target_id}`", parse_mode="Markdown")

async def cmd_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط ادمین‌ها.")
        return
    chat_id = str(update.effective_chat.id)
    full_text = update.message.text.replace("/spem", "", 1).strip()
    if not full_text:
        await update.message.reply_text("`/spem متن1 | متن2 | متن3`", parse_mode="Markdown")
        return
    messages = [m.strip() for m in full_text.split("|") if m.strip()]
    db.setdefault(chat_id, {})
    db[chat_id]["messages"] = messages
    save_db(db)
    await update.message.reply_text(f"✅ {len(messages)} متن ذخیره شد.")

async def spam_loop(chat_id, context):
    sent = 0
    counter = 0
    while active_tasks.get(chat_id, {}).get("running"):
        data = db.get(chat_id, {})
        messages = data.get("messages", [])
        target_id = data.get("target_id")
        target_name = data.get("target_name", "کاربر")
        cfg = data.get("config", {})
        per_round = cfg.get("per_round", 3)
        interval = cfg.get("interval", 10)
        max_total = cfg.get("max_total", 100)
        autodelete = cfg.get("autodelete", 0)
        if not messages:
            break
        for _ in range(per_round):
            if not active_tasks.get(chat_id, {}).get("running"):
                break
            if max_total > 0 and sent >= max_total:
                active_tasks[chat_id]["running"] = False
                await context.bot.send_message(int(chat_id), f"🏁 حداکثر {max_total} پیام. تمام.")
                return
            text = messages[counter % len(messages)]
            counter += 1
            if target_id and str(target_id).startswith("@"):
                tag = f'<a href="https://t.me/{str(target_id)[1:]}">{target_name}</a>'
            elif target_id:
                tag = f'<a href="tg://user?id={target_id}">{target_name}</a>'
            else:
                tag = ""
            try:
                msg = await context.bot.send_message(
                    chat_id=int(chat_id), text=f"{tag} {text}".strip(), parse_mode="HTML"
                )
                sent += 1
                if autodelete > 0:
                    asyncio.create_task(auto_delete(msg, autodelete))
            except Exception as e:
                print(f"خطا: {e}")
                if "Forbidden" in str(e):
                    active_tasks[chat_id]["running"] = False
                    return
            await asyncio.sleep(1)
        for _ in range(interval):
            if not active_tasks.get(chat_id, {}).get("running"):
                return
            await asyncio.sleep(1)

async def auto_delete(msg, seconds):
    await asyncio.sleep(seconds)
    try:
        await msg.delete()
    except Exception:
        pass

async def cmd_set_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط ادمین‌ها.")
        return
    chat_id = str(update.effective_chat.id)
    try:
        interval = int(context.args[0])
        per_round = int(context.args[1])
        max_total = int(context.args[2])
        autodelete = int(context.args[3]) if len(context.args) > 3 else 0
    except (IndexError, ValueError):
        await update.message.reply_text("`/set_config 10 3 100 0`", parse_mode="Markdown")
        return
    db.setdefault(chat_id, {})
    db[chat_id]["config"] = {"interval": interval, "per_round": per_round, "max_total": max_total, "autodelete": autodelete}
    save_db(db)
    await update.message.reply_text("⚙️ تنظیم شد.")

async def cmd_start_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط ادمین‌ها.")
        return
    chat_id = str(update.effective_chat.id)
    data = db.get(chat_id, {})
    if not data.get("target_id"):
        await update.message.reply_text("❌ اول `/id`.", parse_mode="Markdown")
        return
    if not data.get("messages"):
        await update.message.reply_text("❌ اول `/spem`.", parse_mode="Markdown")
        return
    if active_tasks.get(chat_id, {}).get("running"):
        await update.message.reply_text("⚠️ قبلاً فعال.")
        return
    active_tasks[chat_id] = {"running": True}
    await update.message.reply_text("🚀 شروع شد!")
    asyncio.create_task(spam_loop(chat_id, context))

async def cmd_stop_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط ادمین‌ها.")
        return
    chat_id = str(update.effective_chat.id)
    if active_tasks.get(chat_id, {}).get("running"):
        active_tasks[chat_id]["running"] = False
        await update.message.reply_text("🛑 متوقف شد.")
    else:
        await update.message.reply_text("چیزی فعال نبود.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    data = db.get(chat_id, {})
    running = active_tasks.get(chat_id, {}).get("running", False)
    await update.message.reply_text(
        f"📊 آیدی: `{data.get('target_id', '—')}`\n"
        f"متن‌ها: {len(data.get('messages', []))}\n"
        f"وضعیت: {'🟢 فعال' if running else '🔴 خاموش'}",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 دستورها:\n"
        "`/id @user` — ذخیره آیدی\n"
        "`/spem متن1 | متن2 | متن3` — ذخیره متن‌ها\n"
        "`/set_config 10 3 100 0` — تنظیمات\n"
        "`/start_spem` — شروع\n"
        "`/stop_spem` — توقف\n"
        "`/status` — وضعیت\n"
        "⚠️ فقط ادمین‌ها",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("spem", cmd_spem))
    app.add_handler(CommandHandler("set_config", cmd_set_config))
    app.add_handler(CommandHandler("start_spem", cmd_start_spem))
    app.add_handler(CommandHandler("stop_spem", cmd_stop_spem))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))
    
    # وب سرور فیک برای رندر
    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

    def run_health_check():
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()

    threading.Thread(target=run_health_check, daemon=True).start()

    print("✅ ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
