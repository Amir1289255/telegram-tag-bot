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
OWNER_ID = 8217242114

DB_FILE = "db.json"
SHARED_KEY = "shared_data"

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
    return update.effective_user.id in admins

def get_done_keyboard(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ تموم شد، ذخیره کن", callback_data=f"done_{uid}")]])

# ---------- متن ----------
async def cmd_start_collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ فقط توی چت خصوصی ربات کار می‌کنه.")
        return
    if not await is_admin(update, context): return
    uid = update.effective_user.id
    WAITING_FOR_TEXT.add(uid)
    TEMP_TEXTS[uid] = []
    await update.message.reply_text("📝 هر متنی می‌خوای بفرست. آخرش دکمه رو بزن:", reply_markup=get_done_keyboard(uid))

async def cmd_spem_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    messages = db.get(SHARED_KEY, {}).get("messages", [])
    if not messages: return await update.message.reply_text("📭 لیست خالیه.")
    text = "📝 **لیست متن‌ها:**\n\n"
    for i, msg in enumerate(messages, 1): text += f"{i}. {msg}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_clear_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if SHARED_KEY in db and "messages" in db[SHARED_KEY]:
        del db[SHARED_KEY]["messages"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست متن‌ها پاک شد.")

# ---------- گیف ----------
async def cmd_start_collect_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ فقط توی چت خصوصی ربات کار می‌کنه.")
        return
    if not await is_admin(update, context): return
    uid = update.effective_user.id
    WAITING_FOR_GIF.add(uid)
    TEMP_GIFS[uid] = []
    await update.message.reply_text("🎬 هر گیفی می‌خوای بفرست. آخرش دکمه رو بزن:", reply_markup=get_done_keyboard(uid))

async def cmd_list_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    gifs = db.get(SHARED_KEY, {}).get("gifs", [])
    if not gifs: return await update.message.reply_text("📭 لیست خالیه.")
    text = "🎬 **لیست گیف‌ها:**\n"
    for i, gif in enumerate(gifs, 1): text += f"{i}. `{gif[:20]}...`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_remove_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    gifs = db.get(SHARED_KEY, {}).get("gifs", [])
    if not context.args: return await update.message.reply_text("فرمت: `!جینکس_حذف_گیف <شماره>`", parse_mode="Markdown")
    try:
        index = int(context.args[0]) - 1
        if index < 0 or index >= len(gifs): return await update.message.reply_text("❌ شماره نامعتبره.")
        gifs.pop(index)
        db[SHARED_KEY]["gifs"] = gifs
        save_db(db)
        await update.message.reply_text(f"🗑️ گیف شماره {index+1} حذف شد.")
    except: await update.message.reply_text("❌ لطفاً یه عدد بفرست.")

async def cmd_clear_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if SHARED_KEY in db and "gifs" in db[SHARED_KEY]:
        del db[SHARED_KEY]["gifs"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست گیف‌ها پاک شد.")

# ---------- هندل دکمه تموم شد ----------
async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[1])
    if uid != query.from_user.id: return await query.edit_message_text("⛔ مال شما نیست.")

    if uid in WAITING_FOR_TEXT:
        WAITING_FOR_TEXT.remove(uid)
        texts = TEMP_TEXTS.pop(uid, [])
        if not texts: return await query.edit_message_text("❌ هیچ متنی نفرستادی.")
        db.setdefault(SHARED_KEY, {}).setdefault("messages", [])
        added = 0
        for t in texts:
            if t not in db[SHARED_KEY]["messages"]:
                db[SHARED_KEY]["messages"].append(t)
                added += 1
        save_db(db)
        await query.edit_message_text(f"✅ {added} متن ذخیره شد. کل: {len(db[SHARED_KEY]['messages'])}")

    elif uid in WAITING_FOR_GIF:
        WAITING_FOR_GIF.remove(uid)
        gifs = TEMP_GIFS.pop(uid, [])
        if not gifs: return await query.edit_message_text("❌ هیچ گیفی نفرستادی.")
        db.setdefault(SHARED_KEY, {}).setdefault("gifs", [])
        added = 0
        for g in gifs:
            if g not in db[SHARED_KEY]["gifs"]:
                db[SHARED_KEY]["gifs"].append(g)
                added += 1
        save_db(db)
        await query.edit_message_text(f"✅ {added} گیف ذخیره شد. کل: {len(db[SHARED_KEY]['gifs'])}")

# ---------- هندل پیام‌ها ----------
async def handle_incoming_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in WAITING_FOR_TEXT: return
    text = update.message.text.strip()
    if text:
        TEMP_TEXTS[uid].append(text)
        await update.message.reply_text(f"✅ متن {len(TEMP_TEXTS[uid])} دریافت شد.")

async def handle_incoming_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in WAITING_FOR_GIF: return
    if update.message.animation:
        TEMP_GIFS[uid].append(update.message.animation.file_id)
        await update.message.reply_text(f"✅ گیف {len(TEMP_GIFS[uid])} دریافت شد.")

# ---------- بقیه دستورات ----------
async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    targets = []
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        targets.append({"id": user.id, "name": user.first_name or str(user.id)})
    elif context.args:
        for arg in context.args:
            arg_clean = arg.lstrip("@")
            if arg_clean.isdigit(): targets.append({"id": int(arg_clean), "name": arg_clean})
            else: targets.append({"id": f"@{arg_clean}", "name": arg_clean})
    if not targets: return await update.message.reply_text("`!جینکس_ایدی @user` یا ریپلای + `!جینکس_ایدی`", parse_mode="Markdown")
    db.setdefault(SHARED_KEY, {}).setdefault("targets", [])
    existing = [str(t["id"]) for t in db[SHARED_KEY]["targets"]]
    added = 0
    for t in targets:
        if str(t["id"]) not in existing:
            db[SHARED_KEY]["targets"].append(t)
            added += 1
    save_db(db)
    await update.message.reply_text(f"✅ {added} نفر اضافه شد. کل: {len(db[SHARED_KEY]['targets'])}")

async def cmd_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    targets = db.get(SHARED_KEY, {}).get("targets", [])
    if not targets: return await update.message.reply_text("📭 لیست خالیه.")
    text = "🎯 **لیست تگ‌ها:**\n\n"
    for i, t in enumerate(targets, 1): text += f"{i}. {t['name']} (`{t['id']}`)\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_clear_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    if SHARED_KEY in db and "targets" in db[SHARED_KEY]:
        del db[SHARED_KEY]["targets"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست آیدی‌ها پاک شد.")

async def cmd_set_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    try:
        interval, per_round, max_total = int(context.args[0]), int(context.args[1]), int(context.args[2])
        autodelete = int(context.args[3]) if len(context.args) > 3 else 0
    except: return await update.message.reply_text("`!جینکس_تنظیمات 10 3 100 0`", parse_mode="Markdown")
    db.setdefault(SHARED_KEY, {})["config"] = {"interval": interval, "per_round": per_round, "max_total": max_total, "autodelete": autodelete}
    save_db(db)
    await update.message.reply_text("⚙️ تنظیم شد.")

async def cmd_start_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = str(update.effective_chat.id)
    data = db.get(SHARED_KEY, {})
    if not data.get("targets"): return await update.message.reply_text("❌ اول آیدی ذخیره کن.")
    if not data.get("messages") and not data.get("gifs"): return await update.message.reply_text("❌ اول متن یا گیف ذخیره کن.")
    if active_tasks.get(chat_id, {}).get("running"): return await update.message.reply_text("⚠️ قبلاً فعاله.")
    active_tasks[chat_id] = {"running": True}
    await update.message.reply_text("🚀 شروع شد!")
    asyncio.create_task(spam_loop(chat_id, context))

async def cmd_stop_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    chat_id = str(update.effective_chat.id)
    if active_tasks.get(chat_id, {}).get("running"):
        active_tasks[chat_id]["running"] = False
        await update.message.reply_text("🛑 متوقف شد.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context): return
    data = db.get(SHARED_KEY, {})
    running = active_tasks.get(str(update.effective_chat.id), {}).get("running", False)
    await update.message.reply_text(f"📊 آیدی‌ها: {len(data.get('targets', []))}\nمتن‌ها: {len(data.get('messages', []))}\nگیف‌ها: {len(data.get('gifs', []))}\nوضعیت: {'🟢 فعال' if running else '🔴 خاموش'}")

async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args: return
    try:
        new_id = int(context.args[0])
        admins = db.get("allowed_admins", [OWNER_ID])
        if new_id not in admins:
            admins.append(new_id); db["allowed_admins"] = admins; save_db(db)
            await update.message.reply_text(f"✅ {new_id} ادمین شد.")
    except: pass

async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID or not context.args: return
    try:
        rem_id = int(context.args[0])
        admins = db.get("allowed_admins", [OWNER_ID])
        if rem_id in admins and rem_id != OWNER_ID:
            admins.remove(rem_id); db["allowed_admins"] = admins; save_db(db)
            await update.message.reply_text(f"🗑️ {rem_id} حذف شد.")
    except: pass

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **دستورات (با علامت !):**\n"
        "`!جینکس_ایدی` — ذخیره آیدی\n"
        "`!جینکس_تگ‌ها` — لیست تگ‌ها\n"
        "`!جینکس_پاک_ایدی` — پاک کردن آیدی‌ها\n"
        "`!جینکس_متن` — جمع‌آوری متن (فقط PV)\n"
        "`!جینکس_متن‌ها` — لیست متن‌ها\n"
        "`!جینکس_پاک_متن` — پاک کردن متن‌ها\n"
        "`!جینکس_گیف` — جمع‌آوری گیف (فقط PV)\n"
        "`!جینکس_لیست_گیف` — لیست گیف‌ها\n"
        "`!جینکس_حذف_گیف <شماره>` — حذف تک گیف\n"
        "`!جینکس_پاک_گیف` — پاک کردن گیف‌ها\n"
        "`!جینکس_تنظیمات 10 3 100 0` — تنظیمات\n"
        "`!جینکس_شروع` — شروع\n"
        "`!جینکس_توقف` — توقف\n"
        "`!جینکس_وضعیت` — وضعیت\n"
        "`!جینکس_ادمین 123` — ادمین جدید\n"
        "`!جینکس_حذف_ادمین 123` — حذف ادمین",
        parse_mode="Markdown"
    )

async def spam_loop(chat_id, context):
    sent, counter, gif_counter = 0, 0, 0
    while active_tasks.get(chat_id, {}).get("running"):
        data = db.get(SHARED_KEY, {})
        messages, gifs, targets = data.get("messages", []), data.get("gifs", []), data.get("targets", [])
        cfg = data.get("config", {})
        per_round, interval, max_total, autodelete = cfg.get("per_round", 3), cfg.get("interval", 10), cfg.get("max_total", 100), cfg.get("autodelete", 0)
        if not targets: break
        tags = ""
        for t in targets:
            if isinstance(t["id"], str) and t["id"].startswith("@"): tags += f'<a href="https://t.me/{t["id"][1:]}">{t["name"]}</a> '
            elif isinstance(t["id"], int): tags += f'<a href="tg://user?id={t["id"]}">{t["name"]}</a> '
        for _ in range(per_round):
            if not active_tasks.get(chat_id, {}).get("running") or (max_total > 0 and sent >= max_total):
                if max_total > 0 and sent >= max_total: await context.bot.send_message(int(chat_id), f"🏁 حداکثر {max_total} پیام.")
                return
            try:
                if gifs and (counter % 3 == 0):
                    gif_id = gifs[gif_counter % len(gifs)]; gif_counter += 1
                    cap = f"{tags} {messages[counter % len(messages)] if messages else ''}".strip()
                    msg = await context.bot.send_animation(int(chat_id), animation=gif_id, caption=cap, parse_mode="HTML")
                else:
                    if not messages: counter += 1; continue
                    msg = await context.bot.send_message(int(chat_id), text=f"{tags} {messages[counter % len(messages)]}".strip(), parse_mode="HTML")
                sent += 1; counter += 1
                if autodelete > 0: asyncio.create_task(auto_delete(msg, autodelete))
            except Exception as e:
                if "Forbidden" in str(e): active_tasks[chat_id]["running"] = False; return
            await asyncio.sleep(1)
        for _ in range(interval):
            if not active_tasks.get(chat_id, {}).get("running"): return
            await asyncio.sleep(1)

async def auto_delete(msg, seconds):
    await asyncio.sleep(seconds)
    try: await msg.delete()
    except: pass

async def handle_text_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text.startswith("!"): return
    cmd = text[1:].split()[0]
    args = text[1:].split()[1:]
    context.args = args
    if cmd == "جینکس_ایدی": await cmd_id(update, context)
    elif cmd == "جینکس_تگ‌ها": await cmd_targets(update, context)
    elif cmd == "جینکس_پاک_ایدی": await cmd_clear_ids(update, context)
    elif cmd == "جینکس_متن": await cmd_start_collect_text(update, context)
    elif cmd == "جینکس_متن‌ها": await cmd_spem_list(update, context)
    elif cmd == "جینکس_پاک_متن": await cmd_clear_spem(update, context)
    elif cmd == "جینکس_گیف": await cmd_start_collect_gif(update, context)
    elif cmd == "جینکس_لیست_گیف": await cmd_list_gifs(update, context)
    elif cmd == "جینکس_حذف_گیف": await cmd_remove_gif(update, context)
    elif cmd == "جینکس_پاک_گیف": await cmd_clear_gifs(update, context)
    elif cmd == "جینکس_تنظیمات": await cmd_set_config(update, context)
    elif cmd == "جینکس_شروع": await cmd_start_spem(update, context)
    elif cmd == "جینکس_توقف": await cmd_stop_spem(update, context)
    elif cmd == "جینکس_وضعیت": await cmd_status(update, context)
    elif cmd == "جینکس_ادمین": await cmd_add_admin(update, context)
    elif cmd == "جینکس_حذف_ادمین": await cmd_remove_admin(update, context)
    elif cmd == "جینکس" or cmd == "جینکس_راهنما": await cmd_help(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^!'), handle_text_commands))
    app.add_handler(CallbackQueryHandler(handle_done, pattern="^done_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_text))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_incoming_gif))

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

    def run_health_check():
        port = int(os.environ.get("PORT", 8080))
        HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

    threading.Thread(target=run_health_check, daemon=True).start()

    def keep_alive():
        while True:
            time.sleep(300)
            try: urllib.request.urlopen(f"http://127.0.0.1:{int(os.environ.get('PORT', 8080))}")
            except: pass

    threading.Thread(target=keep_alive, daemon=True).start()
    print("✅ ربات جینکس روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
