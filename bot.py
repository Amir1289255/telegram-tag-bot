from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import asyncio
import json
import os
import threading
import urllib.request
import time
import random
from http.server import BaseHTTPRequestHandler, HTTPServer

# ⬇️ این دو خط رو با اطلاعات خودت پر کن ⬇️
TOKEN = "8954928840:AAEnxOYM5D4YlZ9AQQTnVWnZzjjvZNH-hyg"
OWNER_ID = 6112141058

DB_FILE = "db.json"
SHARED_KEY = "shared_data"
WAITING_FOR = {}
TEMP_DATA = {}

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

# ================== سیستم ضدبلاک هوشمند ==================
class SmartAntiBlock:
    def __init__(self):
        self.base_delay = 25
        self.min_delay = 15
        self.max_delay = 45
        self.consecutive_errors = 0
        self.current_delay = self.base_delay

    def get_random_delay(self):
        delay = random.uniform(self.min_delay, self.max_delay)
        if self.consecutive_errors > 0:
            delay += self.consecutive_errors * 10
        return min(delay, self.max_delay + 60)

    def on_error(self, error_msg):
        if "Flood" in error_msg or "Too Many" in error_msg:
            self.consecutive_errors += 1
            self.current_delay = min(self.current_delay + 10, 120)
            return True
        return False

    def on_success(self):
        self.consecutive_errors = max(0, self.consecutive_errors - 1)

# ================== توابع کمکی ==================
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = db.get("allowed_admins", [OWNER_ID])
    return update.effective_user.id in admins

def get_done_keyboard(uid, kind):
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ تموم شد، ذخیره کن", callback_data=f"done_{kind}_{uid}")]])

# ================== جمع‌آوری ==================
async def start_collect(update, context, kind):
    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ فقط توی چت خصوصی ربات کار می‌کنه.")
        return
    if not await is_admin(update, context): return
    uid = update.effective_user.id
    WAITING_FOR[uid] = kind
    TEMP_DATA[uid] = []
    texts = {"text": "📝 هر متنی می‌خوای بفرست...", "gif": "🎬 هر گیفی می‌خوای بفرست...", "sticker": "🖼️ هر استیکری می‌خوای بفرست...", "photo": "📸 هر عکسی می‌خوای بفرست...", "video": "🎥 هر ویدیویی می‌خوای بفرست..."}
    await update.message.reply_text(texts.get(kind, "شروع شد..."), reply_markup=get_done_keyboard(uid, kind))

async def cmd_text(update, context): await start_collect(update, context, "text")
async def cmd_gif(update, context): await start_collect(update, context, "gif")
async def cmd_sticker(update, context): await start_collect(update, context, "sticker")
async def cmd_photo(update, context): await start_collect(update, context, "photo")
async def cmd_video(update, context): await start_collect(update, context, "video")

async def handle_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    kind, uid = parts[1], int(parts[2])
    if uid != query.from_user.id: return await query.edit_message_text("⛔ مال شما نیست.")
    if uid not in WAITING_FOR: return await query.edit_message_text("⚠️ چیزی در انتظار نیست.")
    
    data = TEMP_DATA.pop(uid, [])
    del WAITING_FOR[uid]
    if not data: return await query.edit_message_text("❌ هیچ چیزی نفرستادی.")
    
    db.setdefault(SHARED_KEY, {})
    key = {"text": "messages", "gif": "gifs", "sticker": "stickers", "photo": "photos", "video": "videos"}[kind]
    db[SHARED_KEY].setdefault(key, [])
    added = 0
    for item in data:
        if item not in db[SHARED_KEY][key]:
            db[SHARED_KEY][key].append(item)
            added += 1
    save_db(db)
    await query.edit_message_text(f"✅ {added} {kind} ذخیره شد. کل: {len(db[SHARED_KEY][key])}")

async def handle_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in WAITING_FOR: return
    kind = WAITING_FOR[uid]
    msg = update.message
    if kind == "text" and msg.text: TEMP_DATA[uid].append(msg.text.strip())
    elif kind == "gif" and msg.animation: TEMP_DATA[uid].append(msg.animation.file_id)
    elif kind == "sticker" and msg.sticker: TEMP_DATA[uid].append(msg.sticker.file_id)
    elif kind == "photo" and msg.photo: TEMP_DATA[uid].append(msg.photo[-1].file_id)
    elif kind == "video" and msg.video: TEMP_DATA[uid].append(msg.video.file_id)
    else: return await msg.reply_text("❌ نوع نامعتبر. لطفاً همون نوعی که خواستی بفرست.")
    await msg.reply_text(f"✅ دریافت شد. تعداد: {len(TEMP_DATA[uid])}")

# ================== مدیریت لیست‌ها ==================
async def list_items(update, context, key, title):
    if not await is_admin(update, context): return
    items = db.get(SHARED_KEY, {}).get(key, [])
    if not items: return await update.message.reply_text("📭 لیست خالیه.")
    text = f"**{title}**\n\n"
    for i, item in enumerate(items, 1):
        preview = item if key == "messages" else f"`{item[:20]}...`"
        text += f"{i}. {preview}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_texts_list(update, context): await list_items(update, context, "messages", "📝 لیست متن‌ها")
async def cmd_gifs_list(update, context): await list_items(update, context, "gifs", "🎬 لیست گیف‌ها")
async def cmd_stickers_list(update, context): await list_items(update, context, "stickers", "🖼️ لیست استیکرها")
async def cmd_photos_list(update, context): await list_items(update, context, "photos", "📸 لیست عکس‌ها")
async def cmd_videos_list(update, context): await list_items(update, context, "videos", "🎥 لیست ویدیوها")

async def clear_items(update, context, key, name):
    if not await is_admin(update, context): return
    if SHARED_KEY in db and key in db[SHARED_KEY]:
        del db[SHARED_KEY][key]
        save_db(db)
        await update.message.reply_text(f"🗑️ لیست {name} پاک شد.")

async def cmd_clear_texts(update, context): await clear_items(update, context, "messages", "متن‌ها")
async def cmd_clear_gifs(update, context): await clear_items(update, context, "gifs", "گیف‌ها")
async def cmd_clear_stickers(update, context): await clear_items(update, context, "stickers", "استیکرها")
async def cmd_clear_photos(update, context): await clear_items(update, context, "photos", "عکس‌ها")
async def cmd_clear_videos(update, context): await clear_items(update, context, "videos", "ویدیوها")

# ================== آیدی ==================
async def cmd_id(update, context):
    if not await is_admin(update, context): return
    targets = []
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        targets.append({"id": u.id, "name": u.first_name or str(u.id)})
    elif context.args:
        for arg in context.args:
            a = arg.lstrip("@")
            targets.append({"id": int(a) if a.isdigit() else f"@{a}", "name": a})
    if not targets: return await update.message.reply_text("`.انگشتش کن @user` یا ریپلای + `.انگشتش کن`", parse_mode="Markdown")
    db.setdefault(SHARED_KEY, {}).setdefault("targets", [])
    ex = [str(t["id"]) for t in db[SHARED_KEY]["targets"]]
    added = 0
    for t in targets:
        if str(t["id"]) not in ex:
            db[SHARED_KEY]["targets"].append(t)
            added += 1
    save_db(db)
    await update.message.reply_text(f"✅ {added} نفر انگشت شد. کل: {len(db[SHARED_KEY]['targets'])}")

async def cmd_targets(update, context):
    if not await is_admin(update, context): return
    targets = db.get(SHARED_KEY, {}).get("targets", [])
    if not targets: return await update.message.reply_text("📭 لیست خالیه.")
    text = "🎯 **لیست انگشت‌شده‌ها:**\n\n"
    for i, t in enumerate(targets, 1): text += f"{i}. {t['name']} (`{t['id']}`)\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_clear_ids(update, context):
    if not await is_admin(update, context): return
    if SHARED_KEY in db and "targets" in db[SHARED_KEY]:
        del db[SHARED_KEY]["targets"]; save_db(db)
        await update.message.reply_text("🗑️ لیست انگشت‌شده‌ها پاک شد.")

# ================== شروع و توقف ==================
async def cmd_start(update, context):
    if not await is_admin(update, context): return
    chat_id = str(update.effective_chat.id)
    data = db.get(SHARED_KEY, {})
    if not data.get("targets"): return await update.message.reply_text("❌ اول انگشتش کن.")
    if not any(data.get(k) for k in ["messages", "gifs", "stickers", "photos", "videos"]):
        return await update.message.reply_text("❌ هیچ محتوایی ذخیره نکردی.")
    if active_tasks.get(chat_id, {}).get("running"): return await update.message.reply_text("⚠️ قبلاً فعاله.")
    active_tasks[chat_id] = {"running": True}
    reply_to = update.message.reply_to_message.message_id if update.message.reply_to_message else None
    asyncio.create_task(spam_loop(chat_id, context, reply_to))
    await update.message.reply_text("🚀 بکنش! (شروع شد)")

async def cmd_stop(update, context):
    if not await is_admin(update, context): return
    chat_id = str(update.effective_chat.id)
    if active_tasks.get(chat_id, {}).get("running"):
        active_tasks[chat_id]["running"] = False
        await update.message.reply_text("🛑 نکنش! (متوقف شد)")

async def cmd_status(update, context):
    if not await is_admin(update, context): return
    d = db.get(SHARED_KEY, {})
    running = active_tasks.get(str(update.effective_chat.id), {}).get("running", False)
    await update.message.reply_text(f"📊 انگشت‌شده‌ها: {len(d.get('targets', []))}\nمتن: {len(d.get('messages', []))}\nگیف: {len(d.get('gifs', []))}\nوضعیت: {'🟢 در حال بکنش' if running else '🔴 خاموش'}")

# ================== حلقه اسپم (با ضدبلاک هوشمند) ==================
async def spam_loop(chat_id, context, reply_to=None):
    sent = 0
    smart = SmartAntiBlock()
    
    while active_tasks.get(chat_id, {}).get("running"):
        data = db.get(SHARED_KEY, {})
        messages = data.get("messages", [])
        gifs = data.get("gifs", [])
        stickers = data.get("stickers", [])
        photos = data.get("photos", [])
        videos = data.get("videos", [])
        targets = data.get("targets", [])
        
        if not targets: break
        
        tags = ""
        for t in targets:
            if isinstance(t["id"], str) and t["id"].startswith("@"): tags += f'<a href="https://t.me/{t["id"][1:]}">{t["name"]}</a> '
            elif isinstance(t["id"], int): tags += f'<a href="tg://user?id={t["id"]}">{t["name"]}</a> '

        kinds = []
        if messages: kinds.append("text")
        if gifs: kinds.append("gif")
        if stickers: kinds.append("sticker")
        if photos: kinds.append("photo")
        if videos: kinds.append("video")
        kind = random.choice(kinds)
        
        try:
            send_args = {"chat_id": int(chat_id), "parse_mode": "HTML"}
            if reply_to: send_args["reply_to_message_id"] = reply_to
            
            if kind == "text":
                msg = await context.bot.send_message(text=f"{tags} {random.choice(messages)}", **send_args)
            elif kind == "gif":
                caption = f"{tags} {random.choice(messages) if messages else ''}"
                msg = await context.bot.send_animation(animation=random.choice(gifs), caption=caption.strip(), **send_args)
            elif kind == "sticker":
                msg = await context.bot.send_sticker(sticker=random.choice(stickers), **send_args)
            elif kind == "photo":
                caption = f"{tags} {random.choice(messages) if messages else ''}"
                msg = await context.bot.send_photo(photo=random.choice(photos), caption=caption.strip(), **send_args)
            elif kind == "video":
                caption = f"{tags} {random.choice(messages) if messages else ''}"
                msg = await context.bot.send_video(video=random.choice(videos), caption=caption.strip(), **send_args)
            
            sent += 1
            smart.on_success()
            
            cfg = data.get("config", {})
            autodelete = cfg.get("autodelete", 0)
            if autodelete > 0: asyncio.create_task(auto_delete(msg, autodelete))
            
        except Exception as e:
            err = str(e)
            if smart.on_error(err):
                await asyncio.sleep(60)
            elif "Forbidden" in err:
                active_tasks[chat_id]["running"] = False
                return
        
        delay = smart.get_random_delay()
        for _ in range(int(delay)):
            if not active_tasks.get(chat_id, {}).get("running"): return
            await asyncio.sleep(1)

async def auto_delete(msg, seconds):
    await asyncio.sleep(seconds)
    try: await msg.delete()
    except: pass

# ================== ادمین ==================
async def cmd_add_admin(update, context):
    if update.effective_user.id != OWNER_ID or not context.args: return
    try:
        nid = int(context.args[0])
        admins = db.get("allowed_admins", [OWNER_ID])
        if nid not in admins:
            admins.append(nid); db["allowed_admins"] = admins; save_db(db)
            await update.message.reply_text(f"✅ {nid} ادمین شد.")
    except: pass

async def cmd_remove_admin(update, context):
    if update.effective_user.id != OWNER_ID or not context.args: return
    try:
        rid = int(context.args[0])
        admins = db.get("allowed_admins", [OWNER_ID])
        if rid in admins and rid != OWNER_ID:
            admins.remove(rid); db["allowed_admins"] = admins; save_db(db)
            await update.message.reply_text(f"🗑️ {rid} حذف شد.")
    except: pass

# ================== منوی شیشه‌ای ==================
async def cmd_menu(update, context):
    if not await is_admin(update, context): return
    kb = [
        [InlineKeyboardButton("🚀 بکنش", callback_data="menu_start"), InlineKeyboardButton("🛑 نکنش", callback_data="menu_stop")],
        [InlineKeyboardButton("📊 وضعیت", callback_data="menu_status"), InlineKeyboardButton("📖 راهنما", callback_data="menu_help")],
    ]
    await update.message.reply_text("📱 **منوی مدیریت:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def menu_handler(update, context):
    q = update.callback_query
    await q.answer()
    chat_id = str(q.message.chat.id)
    if q.data == "menu_start":
        data = db.get(SHARED_KEY, {})
        if not data.get("targets"): return await q.edit_message_text("❌ اول انگشتش کن.")
        if active_tasks.get(chat_id, {}).get("running"): return await q.edit_message_text("⚠️ قبلاً فعاله.")
        active_tasks[chat_id] = {"running": True}
        asyncio.create_task(spam_loop(chat_id, context))
        await q.edit_message_text("🚀 بکنش! (شروع شد)")
    elif q.data == "menu_stop":
        if active_tasks.get(chat_id, {}).get("running"):
            active_tasks[chat_id]["running"] = False
            await q.edit_message_text("🛑 نکنش! (متوقف شد)")
        else:
            await q.edit_message_text("⚠️ خاموشه.")
    elif q.data == "menu_status":
        d = db.get(SHARED_KEY, {})
        running = active_tasks.get(chat_id, {}).get("running", False)
        await q.edit_message_text(f"📊 انگشت‌شده‌ها: {len(d.get('targets', []))} | متن: {len(d.get('messages', []))} | وضعیت: {'🟢 در حال بکنش' if running else '🔴 خاموش'}")
    elif q.data == "menu_help":
        await q.edit_message_text("📖 راهنما: `.راهنما` رو بزن.", parse_mode="Markdown")

# ================== راهنمای خوشگل ==================
async def cmd_help(update, context):
    help_text = (
        "╭──────────────────╮\n"
        "   🤖 **راهنمای جامع ربات**\n"
        "╰──────────────────╯\n\n"
        "🚀 **کنترل و اجرا**\n"
        "├ `.بکنش` ➔ شروع اسپم (روی پیام ریپلای کنی، ریپلای میشه)\n"
        "├ `.نکنش` ➔ توقف فوری\n"
        "├ `.وضعیت` ➔ آمار ربات (تعداد متن، گیف و...)\n"
        "└ `.منو` ➔ منوی شیشه‌ای مدیریت\n\n"
        "🎯 **مدیریت آیدی‌ها**\n"
        "├ `.انگشتش کن @user` ➔ ذخیره آیدی (یا ریپلای + دستور)\n"
        "├ `.تگ‌ها` ➔ لیست کسایی که انگشت شدن\n"
        "└ `.پاک_ایدی` ➔ پاک کردن کل لیست آیدی‌ها\n\n"
        "📝 **مدیریت متن‌ها** (فقط چت خصوصی)\n"
        "├ `.متن` ➔ شروع جمع‌آوری متن\n"
        "├ `.متن‌ها` ➔ دیدن لیست متن‌ها\n"
        "└ `.پاک_متن` ➔ حذف همه متن‌ها\n\n"
        "🎬 **مدیریت گیف‌ها** (فقط چت خصوصی)\n"
        "├ `.گیف` ➔ شروع جمع‌آوری گیف\n"
        "├ `.لیست_گیف` ➔ دیدن لیست گیف‌ها\n"
        "└ `.پاک_گیف` ➔ حذف همه گیف‌ها\n\n"
        "🖼️ **مدیریت استیکرها** (فقط چت خصوصی)\n"
        "├ `.استیکر` ➔ شروع جمع‌آوری استیکر\n"
        "├ `.لیست_استیکر` ➔ دیدن لیست استیکرها\n"
        "└ `.پاک_استیکر` ➔ حذف همه استیکرها\n\n"
        "📸 **مدیریت عکس‌ها** (فقط چت خصوصی)\n"
        "├ `.عکس` ➔ شروع جمع‌آوری عکس\n"
        "├ `.لیست_عکس` ➔ دیدن لیست عکس‌ها\n"
        "└ `.پاک_عکس` ➔ حذف همه عکس‌ها\n\n"
        "🎥 **مدیریت ویدیوها** (فقط چت خصوصی)\n"
        "├ `.ویدیو` ➔ شروع جمع‌آوری ویدیو\n"
        "├ `.لیست_ویدیو` ➔ دیدن لیست ویدیوها\n"
        "└ `.پاک_ویدیو` ➔ حذف همه ویدیوها\n\n"
        "👑 **مدیریت ادمین‌ها** (فقط سازنده)\n"
        "├ `.ادمین 123456789` ➔ اضافه کردن ادمین\n"
        "└ `.حذف_ادمین 123456789` ➔ حذف ادمین\n\n"
        "💡 **نکته:** جمع‌آوری محتوا فقط توی چت خصوصی ربات انجام میشه تا گروه شلوغ نشه."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ================== مسیریابی ==================
async def handle_text_cmds(update, context):
    t = update.message.text
    if not t.startswith("."): return
    p = t[1:].split()
    cmd = p[0]
    context.args = p[1:]
    routes = {
        "متن": cmd_text, "گیف": cmd_gif, "استیکر": cmd_sticker, "عکس": cmd_photo, "ویدیو": cmd_video,
        "متن‌ها": cmd_texts_list, "لیست_گیف": cmd_gifs_list, "لیست_استیکر": cmd_stickers_list,
        "لیست_عکس": cmd_photos_list, "لیست_ویدیو": cmd_videos_list,
        "پاک_متن": cmd_clear_texts, "پاک_گیف": cmd_clear_gifs, "پاک_استیکر": cmd_clear_stickers,
        "پاک_عکس": cmd_clear_photos, "پاک_ویدیو": cmd_clear_videos,
        "انگشتش کن": cmd_id, "تگ‌ها": cmd_targets, "پاک_ایدی": cmd_clear_ids,
        "بکنش": cmd_start, "نکنش": cmd_stop, "وضعیت": cmd_status,
        "ادمین": cmd_add_admin, "حذف_ادمین": cmd_remove_admin, "منو": cmd_menu,
        "راهنما": cmd_help,
    }
    if cmd in routes: await routes[cmd](update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^\.'), handle_text_cmds))
    app.add_handler(CallbackQueryHandler(handle_done, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.Regex(r'^\.'), handle_incoming))
    
    class HC(BaseHTTPRequestHandler):
        def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def hc(): HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), HC).serve_forever()
    threading.Thread(target=hc, daemon=True).start()
    def ka():
        while True:
            time.sleep(300)
            try: urllib.request.urlopen(f"http://127.0.0.1:{int(os.environ.get('PORT', 8080))}")
            except: pass
    threading.Thread(target=ka, daemon=True).start()
    print("✅ ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
