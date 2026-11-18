from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import asyncio
import json
import os
import threading
import urllib.request
import time
import random
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# ⬇️ این دو خط رو با اطلاعات خودت پر کن ⬇️
TOKEN = "9151851716:AAHF5Xb2AAkq_BHpwI4K5FtrYPPI7Ma2w1g"
OWNER_ID = 8217242114

DB_FILE = "db.json"
SHARED_KEY = "shared_data"
WAITING_FOR = {}  # برای جمع‌آوری (متن، گیف، استیکر)
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
    if not targets: return await update.message.reply_text("`!جینکس_ایدی @user` یا ریپلای + `!جینکس_ایدی`", parse_mode="Markdown")
    db.setdefault(SHARED_KEY, {}).setdefault("targets", [])
    ex = [str(t["id"]) for t in db[SHARED_KEY]["targets"]]
    added = sum(1 for t in targets if str(t["id"]) not in ex and not db[SHARED_KEY]["targets"].append(t))
    save_db(db)
    await update.message.reply_text(f"✅ اضافه شد. کل: {len(db[SHARED_KEY]['targets'])}")

async def cmd_targets(update, context):
    if not await is_admin(update, context): return
    targets = db.get(SHARED_KEY, {}).get("targets", [])
    if not targets: return await update.message.reply_text("📭 لیست خالیه.")
    text = "🎯 **لیست تگ‌ها:**\n\n"
    for i, t in enumerate(targets, 1): text += f"{i}. {t['name']} (`{t['id']}`)\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_clear_ids(update, context):
    if not await is_admin(update, context): return
    if SHARED_KEY in db and "targets" in db[SHARED_KEY]:
        del db[SHARED_KEY]["targets"]; save_db(db)
        await update.message.reply_text("🗑️ لیست آیدی‌ها پاک شد.")

# ================== تنظیمات و شروع ==================
async def cmd_config(update, context):
    if not await is_admin(update, context): return
    try:
        interval, per_round, max_total = int(context.args[0]), int(context.args[1]), int(context.args[2])
        autodelete = int(context.args[3]) if len(context.args) > 3 else 0
    except: return await update.message.reply_text("`!جینکس_تنظیمات 20 2 80 0`", parse_mode="Markdown")
    db.setdefault(SHARED_KEY, {})["config"] = {"interval": interval, "per_round": per_round, "max_total": max_total, "autodelete": autodelete}
    save_db(db)
    await update.message.reply_text("⚙️ تنظیم شد.")

async def cmd_start(update, context):
    if not await is_admin(update, context): return
    chat_id = str(update.effective_chat.id)
    data = db.get(SHARED_KEY, {})
    if not data.get("targets"): return await update.message.reply_text("❌ اول آیدی ذخیره کن.")
    if not any(data.get(k) for k in ["messages", "gifs", "stickers", "photos", "videos"]):
        return await update.message.reply_text("❌ هیچ محتوایی ذخیره نکردی.")
    if active_tasks.get(chat_id, {}).get("running"): return await update.message.reply_text("⚠️ قبلاً فعاله.")
    active_tasks[chat_id] = {"running": True}
    reply_to = update.message.reply_to_message.message_id if update.message.reply_to_message else None
    asyncio.create_task(spam_loop(chat_id, context, reply_to))
    await update.message.reply_text("🚀 شروع شد!")

async def cmd_stop(update, context):
    if not await is_admin(update, context): return
    chat_id = str(update.effective_chat.id)
    if active_tasks.get(chat_id, {}).get("running"):
        active_tasks[chat_id]["running"] = False
        await update.message.reply_text("🛑 متوقف شد.")

async def cmd_status(update, context):
    if not await is_admin(update, context): return
    d = db.get(SHARED_KEY, {})
    running = active_tasks.get(str(update.effective_chat.id), {}).get("running", False)
    await update.message.reply_text(f"📊 آیدی: {len(d.get('targets', []))}\nمتن: {len(d.get('messages', []))}\nگیف: {len(d.get('gifs', []))}\nاستیکر: {len(d.get('stickers', []))}\nوضعیت: {'🟢 فعال' if running else '🔴 خاموش'}")

# ================== حلقه اسپم (با ضدبلاک و ریپلای) ==================
async def spam_loop(chat_id, context, reply_to=None):
    sent, counter = 0, 0
    while active_tasks.get(chat_id, {}).get("running"):
        data = db.get(SHARED_KEY, {})
        messages = data.get("messages", [])
        gifs = data.get("gifs", [])
        stickers = data.get("stickers", [])
        photos = data.get("photos", [])
        videos = data.get("videos", [])
        targets = data.get("targets", [])
        cfg = data.get("config", {})
        per_round = cfg.get("per_round", 3)
        interval = cfg.get("interval", 20)
        max_total = cfg.get("max_total", 100)
        autodelete = cfg.get("autodelete", 0)
        
        if not targets: break
        
        tags = ""
        for t in targets:
            if isinstance(t["id"], str) and t["id"].startswith("@"):
                tags += f'<a href="https://t.me/{t["id"][1:]}">{t["name"]}</a> '
            elif isinstance(t["id"], int):
                tags += f'<a href="tg://user?id={t["id"]}">{t["name"]}</a> '

        for _ in range(per_round):
            if not active_tasks.get(chat_id, {}).get("running"): break
            if max_total > 0 and sent >= max_total:
                active_tasks[chat_id]["running"] = False
                await context.bot.send_message(int(chat_id), f"🏁 حداکثر {max_total} پیام.")
                return
            
            try:
                # انتخاب تصادفی نوع محتوا
                kinds = []
                if messages: kinds.append("text")
                if gifs: kinds.append("gif")
                if stickers: kinds.append("sticker")
                if photos: kinds.append("photo")
                if videos: kinds.append("video")
                kind = random.choice(kinds)
                send_args = {"chat_id": int(chat_id), "parse_mode": "HTML"}
                if reply_to: send_args["reply_to_message_id"] = reply_to
                
                if kind == "text":
                    text = f"{tags} {random.choice(messages)}"
                    msg = await context.bot.send_message(text=text, **send_args)
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
                if autodelete > 0: asyncio.create_task(auto_delete(msg, autodelete))
            except Exception as e:
                err = str(e)
                if "Flood" in err or "Too Many" in err:
                    # استخراج زمان صبر از پیام خطا
                    wait = 30
                    if "seconds" in err:
                        try: wait = int(err.split("seconds")[0].split()[-1]) + 5
                        except: pass
                    await asyncio.sleep(wait)
                elif "Forbidden" in err:
                    active_tasks[chat_id]["running"] = False
                    return
            
            # تاخیر تصادفی بین پیام‌ها (1-3 ثانیه)
            await asyncio.sleep(random.uniform(1, 3))
        
        # تاخیر تصادفی بین دورها (80% تا 120% مقدار تنظیم)
        delay = interval * random.uniform(0.8, 1.2)
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
        [InlineKeyboardButton("🚀 شروع", callback_data="menu_start"), InlineKeyboardButton("🛑 توقف", callback_data="menu_stop")],
        [InlineKeyboardButton("📊 وضعیت", callback_data="menu_status"), InlineKeyboardButton("📖 راهنما", callback_data="menu_help")],
    ]
    await update.message.reply_text("📱 **منوی مدیریت:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def menu_handler(update, context):
    q = update.callback_query
    await q.answer()
    chat_id = str(q.message.chat.id)
    if q.data == "menu_start":
        data = db.get(SHARED_KEY, {})
        if not data.get("targets"): return await q.edit_message_text("❌ اول آیدی ذخیره کن.")
        if active_tasks.get(chat_id, {}).get("running"): return await q.edit_message_text("⚠️ قبلاً فعاله.")
        active_tasks[chat_id] = {"running": True}
        asyncio.create_task(spam_loop(chat_id, context))
        await q.edit_message_text("🚀 شروع شد!")
    elif q.data == "menu_stop":
        if active_tasks.get(chat_id, {}).get("running"):
            active_tasks[chat_id]["running"] = False
            await q.edit_message_text("🛑 متوقف شد.")
        else:
            await q.edit_message_text("⚠️ خاموشه.")
    elif q.data == "menu_status":
        d = db.get(SHARED_KEY, {})
        running = active_tasks.get(chat_id, {}).get("running", False)
        await q.edit_message_text(f"📊 آیدی: {len(d.get('targets', []))} | متن: {len(d.get('messages', []))} | وضعیت: {'🟢' if running else '🔴'}")
    elif q.data == "menu_help":
        await q.edit_message_text("📖 راهنما رو توی چت بزن: `!جینکس_راهنما`", parse_mode="Markdown")

# ================== راهنما ==================
async def cmd_help(update, context):
    await update.message.reply_text(
        "📖 **دستورات جینکس افسانه‌ای:**\n\n"
        "**مدیریت محتوا:**\n"
        "`!جینکس_متن` — جمع‌آوری متن\n"
        "`!جینکس_گیف` — جمع‌آوری گیف\n"
        "`!جینکس_استیکر` — جمع‌آوری استیکر\n"
        "`!جینکس_عکس` — جمع‌آوری عکس\n"
        "`!جینکس_ویدیو` — جمع‌آوری ویدیو\n\n"
        "**نمایش و پاک کردن:**\n"
        "`!جینکس_متن‌ها` / `!جینکس_پاک_متن`\n"
        "`!جینکس_لیست_گیف` / `!جینکس_پاک_گیف`\n"
        "`!جینکس_لیست_استیکر` / `!جینکس_پاک_استیکر`\n"
        "`!جینکس_لیست_عکس` / `!جینکس_پاک_عکس`\n"
        "`!جینکس_لیست_ویدیو` / `!جینکس_پاک_ویدیو`\n\n"
        "**آیدی و تنظیمات:**\n"
        "`!جینکس_ایدی @user` — ذخیره آیدی\n"
        "`!جینکس_تگ‌ها` / `!جینکس_پاک_ایدی`\n"
        "`!جینکس_تنظیمات 20 2 80 0`\n\n"
        "**اجرا:**\n"
        "`!جینکس_شروع` (یا ریپلای + شروع)\n"
        "`!جینکس_توقف`\n"
        "`!جینکس_وضعیت`\n"
        "`!جینکس_منو` — منوی شیشه‌ای\n\n"
        "**ادمین:**\n"
        "`!جینکس_ادمین 123` / `!جینکس_حذف_ادمین 123`",
        parse_mode="Markdown"
    )

# ================== مسیریابی دستورات ==================
async def handle_text_cmds(update, context):
    t = update.message.text
    if not t.startswith("!"): return
    p = t[1:].split()
    cmd = p[0]
    context.args = p[1:]
    routes = {
        "جینکس_متن": cmd_text, "جینکس_گیف": cmd_gif, "جینکس_استیکر": cmd_sticker, "جینکس_عکس": cmd_photo, "جینکس_ویدیو": cmd_video,
        "جینکس_متن‌ها": cmd_texts_list, "جینکس_لیست_گیف": cmd_gifs_list, "جینکس_لیست_استیکر": cmd_stickers_list,
        "جینکس_لیست_عکس": cmd_photos_list, "جینکس_لیست_ویدیو": cmd_videos_list,
        "جینکس_پاک_متن": cmd_clear_texts, "جینکس_پاک_گیف": cmd_clear_gifs, "جینکس_پاک_استیکر": cmd_clear_stickers,
        "جینکس_پاک_عکس": cmd_clear_photos, "جینکس_پاک_ویدیو": cmd_clear_videos,
        "جینکس_ایدی": cmd_id, "جینکس_تگ‌ها": cmd_targets, "جینکس_پاک_ایدی": cmd_clear_ids,
        "جینکس_تنظیمات": cmd_config, "جینکس_شروع": cmd_start, "جینکس_توقف": cmd_stop, "جینکس_وضعیت": cmd_status,
        "جینکس_ادمین": cmd_add_admin, "جینکس_حذف_ادمین": cmd_remove_admin, "جینکس_منو": cmd_menu,
        "جینکس": cmd_help, "جینکس_راهنما": cmd_help,
    }
    if cmd in routes: await routes[cmd](update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^!'), handle_text_cmds))
    app.add_handler(CallbackQueryHandler(handle_done, pattern="^done_"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^menu_"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.Regex(r'^!'), handle_incoming))
    
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
    print("✅ جینکس افسانه‌ای روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
