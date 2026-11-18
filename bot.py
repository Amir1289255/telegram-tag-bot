from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import asyncio
import json
import os
import threading
import urllib.request
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# ⬇️ این دو خط رو با اطلاعات خودت پر کن ⬇️
TOKEN = "9151851716:AAHF5Xb2AAkq_BHpwI4K5FtrYPPI7Ma2w1g"
OWNER_ID = 8217242114  # آیدی عددی خودت

DB_FILE = "db.json"
SHARED_KEY = "shared_data"

# حالت‌های موقت (فقط توی حافظه)
WAITING_FOR_TEXT = set()
WAITING_FOR_GIF = set()
TEMP_TEXTS = {}
TEMP_GIFS = {}

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

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = db.get("allowed_admins", [OWNER_ID])
    if update.effective_user.id in admins:
        return True
    return False

# ---------- دکمه شیشه‌ای ----------
def get_done_keyboard(uid):
    keyboard = [[InlineKeyboardButton("✅ تموم شد، ذخیره کن", callback_data=f"done_{uid}")]]
    return InlineKeyboardMarkup(keyboard)

# ---------- شروع جمع‌آوری متن ----------
async def cmd_start_collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ این دستور فقط توی چت خصوصی ربات کار می‌کنه.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    uid = update.effective_user.id
    WAITING_FOR_TEXT.add(uid)
    TEMP_TEXTS[uid] = []
    await update.message.reply_text(
        "📝 هر متنی که می‌خوای رو یکی‌یکی بفرست. وقتی همه رو فرستادی، روی دکمه زیر بزن:",
        reply_markup=get_done_keyboard(uid)
    )

# ---------- شروع جمع‌آوری گیف ----------
async def cmd_start_collect_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ این دستور فقط توی چت خصوصی ربات کار می‌کنه.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    uid = update.effective_user.id
    WAITING_FOR_GIF.add(uid)
    TEMP_GIFS[uid] = []
    await update.message.reply_text(
        "🎬 هر گیفی که می‌خوای رو یکی‌یکی بفرست. وقتی همه رو فرستادی، روی دکمه زیر بزن:",
        reply_markup=get_done_keyboard(uid)
    )

# ---------- هندل کردن دکمه تموم شد ----------
async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[1])
    
    if uid != query.from_user.id:
        await query.edit_message_text("⛔ این دکمه مال شما نیست.")
        return

    if uid in WAITING_FOR_TEXT:
        WAITING_FOR_TEXT.remove(uid)
        texts = TEMP_TEXTS.pop(uid, [])
        if not texts:
            await query.edit_message_text("❌ هیچ متنی نفرستادی.")
            return
        db.setdefault(SHARED_KEY, {})
        if "messages" not in db[SHARED_KEY]:
            db[SHARED_KEY]["messages"] = []
        added = 0
        for t in texts:
            if t not in db[SHARED_KEY]["messages"]:
                db[SHARED_KEY]["messages"].append(t)
                added += 1
        save_db(db)
        await query.edit_message_text(f"✅ {added} متن ذخیره شد. کل متن‌ها: {len(db[SHARED_KEY]['messages'])}")

    elif uid in WAITING_FOR_GIF:
        WAITING_FOR_GIF.remove(uid)
        gifs = TEMP_GIFS.pop(uid, [])
        if not gifs:
            await query.edit_message_text("❌ هیچ گیفی نفرستادی.")
            return
        db.setdefault(SHARED_KEY, {})
        if "gifs" not in db[SHARED_KEY]:
            db[SHARED_KEY]["gifs"] = []
        added = 0
        for g in gifs:
            if g not in db[SHARED_KEY]["gifs"]:
                db[SHARED_KEY]["gifs"].append(g)
                added += 1
        save_db(db)
        await query.edit_message_text(f"✅ {added} گیف ذخیره شد. کل گیف‌ها: {len(db[SHARED_KEY]['gifs'])}")

# ---------- دریافت متن توی حالت جمع‌آوری ----------
async def handle_incoming_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in WAITING_FOR_TEXT:
        return
    text = update.message.text.strip()
    if text:
        TEMP_TEXTS[uid].append(text)
        await update.message.reply_text(f"✅ متن {len(TEMP_TEXTS[uid])} دریافت شد. بعدی رو بفرست یا دکمه تموم شد رو بزن.")

# ---------- دریافت گیف توی حالت جمع‌آوری ----------
async def handle_incoming_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in WAITING_FOR_GIF:
        return
    if update.message.animation:
        file_id = update.message.animation.file_id
        TEMP_GIFS[uid].append(file_id)
        await update.message.reply_text(f"✅ گیف {len(TEMP_GIFS[uid])} دریافت شد. بعدی رو بفرست یا دکمه تموم شد رو بزن.")
    else:
        await update.message.reply_text("❌ لطفاً یک گیف بفرست (نه عکس یا ویدیو).")

# ---------- نمایش لیست‌ها ----------
async def cmd_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    targets = db.get(SHARED_KEY, {}).get("targets", [])
    if not targets:
        await update.message.reply_text("📭 لیست خالیه.")
        return
    text = "🎯 **لیست تگ‌ها:**\n\n"
    for i, t in enumerate(targets, 1):
        text += f"{i}. {t['name']} (`{t['id']}`)\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_spem_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    messages = db.get(SHARED_KEY, {}).get("messages", [])
    if not messages:
        await update.message.reply_text("📭 لیست متن‌ها خالیه.")
        return
    text = "📝 **لیست متن‌ها:**\n\n"
    for i, msg in enumerate(messages, 1):
        text += f"{i}. {msg}\n"
    await update.message.reply_text(text)

async def cmd_list_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    gifs = db.get(SHARED_KEY, {}).get("gifs", [])
    if not gifs:
        await update.message.reply_text("📭 لیست گیف‌ها خالیه.")
        return
    text = "🎬 **لیست گیف‌ها:**\n"
    for i, gif in enumerate(gifs, 1):
        text += f"{i}. `{gif[:20]}...`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ---------- ذخیره آیدی، حذف‌ها و... (همون قبلی‌ها) ----------
async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    targets = []
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        targets.append({"id": user.id, "name": user.first_name or user.username or str(user.id)})
    elif context.args:
        for arg in context.args:
            arg_clean = arg.lstrip("@")
            if arg_clean.isdigit():
                targets.append({"id": int(arg_clean), "name": arg_clean})
            else:
                targets.append({"id": f"@{arg_clean}", "name": arg_clean})
    else:
        await update.message.reply_text("`/جینکس_ایدی @user` یا ریپلای کن و بزن `/جینکس_ایدی`", parse_mode="Markdown")
        return

    if not targets:
        await update.message.reply_text("❌ آیدی معتبری پیدا نشد.")
        return

    db.setdefault(SHARED_KEY, {})
    if "targets" not in db[SHARED_KEY]:
        db[SHARED_KEY]["targets"] = []
    existing_ids = [str(t["id"]) for t in db[SHARED_KEY]["targets"]]
    added = 0
    for t in targets:
        if str(t["id"]) not in existing_ids:
            db[SHARED_KEY]["targets"].append(t)
            added += 1
    save_db(db)
    total = len(db[SHARED_KEY]["targets"])
    await update.message.reply_text(f"✅ {added} نفر اضافه شد. کل: {total} نفر")

async def cmd_clear_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if SHARED_KEY in db and "targets" in db[SHARED_KEY]:
        del db[SHARED_KEY]["targets"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست آیدی‌ها پاک شد.")

async def cmd_clear_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if SHARED_KEY in db and "messages" in db[SHARED_KEY]:
        del db[SHARED_KEY]["messages"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست متن‌ها پاک شد.")

async def cmd_clear_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    if SHARED_KEY in db and "gifs" in db[SHARED_KEY]:
        del db[SHARED_KEY]["gifs"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست گیف‌ها پاک شد.")

async def cmd_remove_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    gifs = db.get(SHARED_KEY, {}).get("gifs", [])
    if not context.args:
        await update.message.reply_text("فرمت: `/جینکس_حذف_گیف <شماره>`", parse_mode="Markdown")
        return
    try:
        index = int(context.args[0]) - 1
        if index < 0 or index >= len(gifs):
            await update.message.reply_text("❌ شماره نامعتبره.")
            return
        gifs.pop(index)
        db[SHARED_KEY]["gifs"] = gifs
        save_db(db)
        await update.message.reply_text(f"🗑️ گیف شماره {index+1} حذف شد.")
    except ValueError:
        await update.message.reply_text("❌ لطفاً یه عدد بفرست.")

# ---------- تنظیمات، شروع و توقف، وضعیت، ادمین‌ها، راهنما ----------
async def cmd_set_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    try:
        interval = int(context.args[0])
        per_round = int(context.args[1])
        max_total = int(context.args[2])
        autodelete = int(context.args[3]) if len(context.args) > 3 else 0
    except (IndexError, ValueError):
        await update.message.reply_text("`/جینکس_تنظیمات 10 3 100 0`", parse_mode="Markdown")
        return
    db.setdefault(SHARED_KEY, {})
    db[SHARED_KEY]["config"] = {"interval": interval, "per_round": per_round, "max_total": max_total, "autodelete": autodelete}
    save_db(db)
    await update.message.reply_text("⚙️ تنظیم شد.")

async def cmd_start_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    chat_id = str(update.effective_chat.id)
    data = db.get(SHARED_KEY, {})
    if not data.get("targets"):
        await update.message.reply_text("❌ اول آیدی ذخیره کن.")
        return
    if not data.get("messages") and not data.get("gifs"):
        await update.message.reply_text("❌ اول متن یا گیف ذخیره کن.")
        return
    if active_tasks.get(chat_id, {}).get("running"):
        await update.message.reply_text("⚠️ قبلاً فعاله.")
        return
    active_tasks[chat_id] = {"running": True}
    await update.message.reply_text("🚀 شروع شد!")
    asyncio.create_task(spam_loop(chat_id, context))

async def cmd_stop_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    chat_id = str(update.effective_chat.id)
    if active_tasks.get(chat_id, {}).get("running"):
        active_tasks[chat_id]["running"] = False
        await update.message.reply_text("🛑 متوقف شد.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    data = db.get(SHARED_KEY, {})
    chat_id = str(update.effective_chat.id)
    running = active_tasks.get(chat_id, {}).get("running", False)
    await update.message.reply_text(
        f"📊 آیدی‌ها: {len(data.get('targets', []))}\n"
        f"متن‌ها: {len(data.get('messages', []))}\n"
        f"گیف‌ها: {len(data.get('gifs', []))}\n"
        f"وضعیت: {'🟢 فعال' if running else '🔴 خاموش'}"
    )

async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        return
    try:
        new_id = int(context.args[0])
        admins = db.get("allowed_admins", [OWNER_ID])
        if new_id not in admins:
            admins.append(new_id)
            db["allowed_admins"] = admins
            save_db(db)
            await update.message.reply_text(f"✅ {new_id} ادمین شد.")
    except:
        pass

async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not context.args:
        return
    try:
        rem_id = int(context.args[0])
        admins = db.get("allowed_admins", [OWNER_ID])
        if rem_id in admins and rem_id != OWNER_ID:
            admins.remove(rem_id)
            db["allowed_admins"] = admins
            save_db(db)
            await update.message.reply_text(f"🗑️ {rem_id} حذف شد.")
    except:
        pass

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **دستورات جینکس:**\n"
        "`/جینکس` — همین راهنما\n"
        "`/جینکس_ایدی` — ذخیره آیدی\n"
        "`/جینکس_تگ‌ها` — لیست تگ‌ها\n"
        "`/جینکس_پاک_ایدی` — پاک کردن لیست آیدی\n"
        "`/جینکس_متن` — شروع جمع‌آوری متن (فقط PV)\n"
        "`/جینکس_متن‌ها` — لیست متن‌ها\n"
        "`/جینکس_پاک_متن` — پاک کردن متن‌ها\n"
        "`/جینکس_گیف` — شروع جمع‌آوری گیف (فقط PV)\n"
        "`/جینکس_لیست_گیف` — لیست گیف‌ها\n"
        "`/جینکس_حذف_گیف <شماره>` — حذف تک گیف\n"
        "`/جینکس_پاک_گیف` — پاک کردن کل گیف‌ها\n"
        "`/جینکس_تنظیمات 10 3 100 0` — تنظیمات\n"
        "`/جینکس_شروع` — شروع\n"
        "`/جینکس_توقف` — توقف\n"
        "`/جینکس_وضعیت` — وضعیت\n"
        "`/جینکس_ادمین 123456789` — اضافه کردن ادمین\n"
        "`/جینکس_حذف_ادمین 123456789` — حذف ادمین",
        parse_mode="Markdown"
    )

# ---------- حلقه اسپم ----------
async def spam_loop(chat_id, context):
    sent = 0
    counter = 0
    gif_counter = 0
    while active_tasks.get(chat_id, {}).get("running"):
        data = db.get(SHARED_KEY, {})
        messages = data.get("messages", [])
        gifs = data.get("gifs", [])
        targets = data.get("targets", [])
        cfg = data.get("config", {})
        per_round = cfg.get("per_round", 3)
        interval = cfg.get("interval", 10)
        max_total = cfg.get("max_total", 100)
        autodelete = cfg.get("autodelete", 0)
        if not targets: break
        
        tags_html = ""
        for t in targets:
            if isinstance(t["id"], str) and t["id"].startswith("@"):
                tags_html += f'<a href="https://t.me/{t["id"][1:]}">{t["name"]}</a> '
            elif isinstance(t["id"], int):
                tags_html += f'<a href="tg://user?id={t["id"]}">{t["name"]}</a> '

        for _ in range(per_round):
            if not active_tasks.get(chat_id, {}).get("running"): break
            if max_total > 0 and sent >= max_total:
                active_tasks[chat_id]["running"] = False
                await context.bot.send_message(int(chat_id), f"🏁 حداکثر {max_total} پیام. تمام.")
                return
            send_gif = bool(gifs and (counter % 3 == 0))
            try:
                if send_gif:
                    gif_id = gifs[gif_counter % len(gifs)]
                    gif_counter += 1
                    caption = f"{tags_html} {messages[counter % len(messages)] if messages else ''}".strip()
                    msg = await context.bot.send_animation(chat_id=int(chat_id), animation=gif_id, caption=caption, parse_mode="HTML")
                else:
                    if not messages:
                        counter += 1
                        continue
                    msg = await context.bot.send_message(chat_id=int(chat_id), text=f"{tags_html} {messages[counter % len(messages)]}".strip(), parse_mode="HTML")
                sent += 1
                counter += 1
                if autodelete > 0:
                    asyncio.create_task(auto_delete(msg, autodelete))
            except Exception as e:
                if "Forbidden" in str(e):
                    active_tasks[chat_id]["running"] = False
                    return
            await asyncio.sleep(1)
        for _ in range(interval):
            if not active_tasks.get(chat_id, {}).get("running"): return
            await asyncio.sleep(1)

async def auto_delete(msg, seconds):
    await asyncio.sleep(seconds)
    try: await msg.delete()
    except: pass

def main():
    app = Application.builder().token(TOKEN).build()
    
    # هندلرهای اصلی
    app.add_handler(CommandHandler("جینکس", cmd_help))
    app.add_handler(CommandHandler("جینکس_ایدی", cmd_id))
    app.add_handler(CommandHandler("جینکس_تگ‌ها", cmd_targets))
    app.add_handler(CommandHandler("جینکس_پاک_ایدی", cmd_clear_ids))
    app.add_handler(CommandHandler("جینکس_متن", cmd_start_collect_text))
    app.add_handler(CommandHandler("جینکس_متن‌ها", cmd_spem_list))
    app.add_handler(CommandHandler("جینکس_پاک_متن", cmd_clear_spem))
    app.add_handler(CommandHandler("جینکس_گیف", cmd_start_collect_gif))
    app.add_handler(CommandHandler("جینکس_لیست_گیف", cmd_list_gifs))
    app.add_handler(CommandHandler("جینکس_حذف_گیف", cmd_remove_gif))
    app.add_handler(CommandHandler("جینکس_پاک_گیف", cmd_clear_gifs))
    app.add_handler(CommandHandler("جینکس_تنظیمات", cmd_set_config))
    app.add_handler(CommandHandler("جینکس_شروع", cmd_start_spem))
    app.add_handler(CommandHandler("جینکس_توقف", cmd_stop_spem))
    app.add_handler(CommandHandler("جینکس_وضعیت", cmd_status))
    app.add_handler(CommandHandler("جینکس_ادمین", cmd_add_admin))
    app.add_handler(CommandHandler("جینکس_حذف_ادمین", cmd_remove_admin))

    # دکمه شیشه‌ای
    app.add_handler(CallbackQueryHandler(handle_done, pattern="^done_"))
    
    # هندلرهای پیام‌های متنی و گیف
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_text))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_incoming_gif))

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
    
    def keep_alive():
        while True:
            time.sleep(300)
            try:
                port = int(os.environ.get("PORT", 8080))
                urllib.request.urlopen(f"http://127.0.0.1:{port}")
            except: pass

    threading.Thread(target=keep_alive, daemon=True).start()

    print("✅ ربات جینکس روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
