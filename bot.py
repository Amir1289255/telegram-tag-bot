from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio
import json
import os
import threading
import urllib.request
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

# ⬇️ این دو خط رو با اطلاعات خودت پر کن ⬇️
TOKEN = "9151851716:AAHF5Xb2AAkq_BHpwI4K5FtrYPPI7Ma2w1g"
OWNER_ID = 8217242114  # آیدی عددی خودت رو اینجا بذار

DB_FILE = "db.json"
WAITING_FOR_GIF = {}

# کلید مشترک برای همه گروه‌ها
SHARED_KEY = "shared_data"

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

# ---------- ذخیره آیدی‌ها (مشترک) ----------
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
        await update.message.reply_text("`/id @user` یا `/id 123456789` یا ریپلای + `/id`", parse_mode="Markdown")
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
    await update.message.reply_text(f"✅ {added} نفر اضافه شد. کل لیست: {total} نفر")

# ---------- نمایش لیست آیدی‌ها ----------
async def cmd_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    targets = db.get(SHARED_KEY, {}).get("targets", [])
    if not targets:
        await update.message.reply_text("📭 لیست خالیه. اول با `/id` آیدی اضافه کن.", parse_mode="Markdown")
        return
    text = "🎯 **لیست کسانی که تگ میشن:**\n\n"
    for i, t in enumerate(targets, 1):
        text += f"{i}. {t['name']} (`{t['id']}`)\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ---------- پاک کردن لیست آیدی‌ها ----------
async def cmd_clear_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    if SHARED_KEY in db and "targets" in db[SHARED_KEY]:
        del db[SHARED_KEY]["targets"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست آیدی‌ها پاک شد.")
    else:
        await update.message.reply_text("❌ لیستی برای پاک کردن وجود ندارد.")

# ---------- ذخیره متن‌ها (مشترک) ----------
async def cmd_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    full_text = update.message.text.replace("/spem", "", 1).strip()
    if not full_text:
        await update.message.reply_text("`/spem متن1 | متن2 | متن3`", parse_mode="Markdown")
        return
    new_messages = [m.strip() for m in full_text.split("|") if m.strip()]
    db.setdefault(SHARED_KEY, {})
    if "messages" not in db[SHARED_KEY]:
        db[SHARED_KEY]["messages"] = []
    added = 0
    for msg in new_messages:
        if msg not in db[SHARED_KEY]["messages"]:
            db[SHARED_KEY]["messages"].append(msg)
            added += 1
    save_db(db)
    total = len(db[SHARED_KEY]["messages"])
    await update.message.reply_text(f"✅ {added} متن اضافه شد. کل متن‌ها: {total}")

# ---------- ذخیره گیف (مشترک) ----------
async def cmd_add_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    WAITING_FOR_GIF[update.effective_chat.id] = True
    await update.message.reply_text("🎬 حالا گیف مورد نظرت رو بفرست تا ذخیره کنم.")

async def handle_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not WAITING_FOR_GIF.get(chat_id):
        return
    if update.message.animation:
        file_id = update.message.animation.file_id
        db.setdefault(SHARED_KEY, {})
        if "gifs" not in db[SHARED_KEY]:
            db[SHARED_KEY]["gifs"] = []
        if file_id not in db[SHARED_KEY]["gifs"]:
            db[SHARED_KEY]["gifs"].append(file_id)
            save_db(db)
            await update.message.reply_text(f"✅ گیف ذخیره شد. کل گیف‌ها: {len(db[SHARED_KEY]['gifs'])}")
        else:
            await update.message.reply_text("⚠️ این گیف از قبل ذخیره شده بود.")
        del WAITING_FOR_GIF[chat_id]
    else:
        await update.message.reply_text("❌ لطفاً یک گیف بفرست (نه عکس یا ویدیو).")

# ---------- نمایش لیست گیف‌ها ----------
async def cmd_list_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    gifs = db.get(SHARED_KEY, {}).get("gifs", [])
    if not gifs:
        await update.message.reply_text("📭 لیست گیف‌ها خالیه.", parse_mode="Markdown")
        return
    text = "🎬 **لیست گیف‌ها:**\n"
    for i, gif in enumerate(gifs, 1):
        text += f"{i}. `{gif[:20]}...`\n"
    text += "\nبرای حذف: `/remove_gif <شماره>`"
    await update.message.reply_text(text, parse_mode="Markdown")

# ---------- حذف تک گیف ----------
async def cmd_remove_gif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    gifs = db.get(SHARED_KEY, {}).get("gifs", [])
    if not gifs:
        await update.message.reply_text("📭 لیست گیف‌ها خالیه.")
        return
    if not context.args:
        await update.message.reply_text("فرمت: `/remove_gif <شماره>`", parse_mode="Markdown")
        return
    try:
        index = int(context.args[0]) - 1
        if index < 0 or index >= len(gifs):
            await update.message.reply_text("❌ شماره نامعتبره.")
            return
        gifs.pop(index)
        db[SHARED_KEY]["gifs"] = gifs
        save_db(db)
        await update.message.reply_text(f"🗑️ گیف شماره {index+1} حذف شد. کل گیف‌ها: {len(gifs)}")
    except ValueError:
        await update.message.reply_text("❌ لطفاً یه عدد بفرست.")

# ---------- پاک کردن کل گیف‌ها ----------
async def cmd_clear_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    if SHARED_KEY in db and "gifs" in db[SHARED_KEY]:
        del db[SHARED_KEY]["gifs"]
        save_db(db)
        await update.message.reply_text("🗑️ کل لیست گیف‌ها پاک شد.")
    else:
        await update.message.reply_text("❌ لیستی برای پاک کردن وجود ندارد.")

# ---------- نمایش لیست متن‌ها ----------
async def cmd_spem_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    messages = db.get(SHARED_KEY, {}).get("messages", [])
    if not messages:
        await update.message.reply_text("📭 لیست متن‌ها خالیه.", parse_mode="Markdown")
        return
    text = "📝 **لیست متن‌ها:**\n\n"
    for i, msg in enumerate(messages, 1):
        text += f"{i}. {msg}\n"
    await update.message.reply_text(text)

# ---------- پاک کردن لیست متن‌ها ----------
async def cmd_clear_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    if SHARED_KEY in db and "messages" in db[SHARED_KEY]:
        del db[SHARED_KEY]["messages"]
        save_db(db)
        await update.message.reply_text("🗑️ لیست متن‌ها پاک شد.")
    else:
        await update.message.reply_text("❌ لیستی برای پاک کردن وجود ندارد.")

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
        if not targets:
            break
        tags_html = ""
        for t in targets:
            if isinstance(t["id"], str) and t["id"].startswith("@"):
                tags_html += f'<a href="https://t.me/{t["id"][1:]}">{t["name"]}</a> '
            elif isinstance(t["id"], int):
                tags_html += f'<a href="tg://user?id={t["id"]}">{t["name"]}</a> '
            else:
                tags_html += f'{t["name"]} '

        for _ in range(per_round):
            if not active_tasks.get(chat_id, {}).get("running"):
                break
            if max_total > 0 and sent >= max_total:
                active_tasks[chat_id]["running"] = False
                await context.bot.send_message(int(chat_id), f"🏁 حداکثر {max_total} پیام. تمام.")
                return
            send_gif = False
            if gifs and (counter % 3 == 0):
                send_gif = True
            try:
                if send_gif:
                    gif_id = gifs[gif_counter % len(gifs)]
                    gif_counter += 1
                    caption = f"{tags_html} {messages[counter % len(messages)] if messages else ''}".strip()
                    msg = await context.bot.send_animation(
                        chat_id=int(chat_id), animation=gif_id, caption=caption, parse_mode="HTML"
                    )
                else:
                    if not messages:
                        counter += 1
                        continue
                    text = messages[counter % len(messages)]
                    msg = await context.bot.send_message(
                        chat_id=int(chat_id), text=f"{tags_html} {text}".strip(), parse_mode="HTML"
                    )
                sent += 1
                counter += 1
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

# ---------- تنظیمات ----------
async def cmd_set_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    try:
        interval = int(context.args[0])
        per_round = int(context.args[1])
        max_total = int(context.args[2])
        autodelete = int(context.args[3]) if len(context.args) > 3 else 0
    except (IndexError, ValueError):
        await update.message.reply_text("`/set_config 10 3 100 0`", parse_mode="Markdown")
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
        await update.message.reply_text("❌ اول با `/id` آیدی‌ها را ذخیره کن.", parse_mode="Markdown")
        return
    if not data.get("messages") and not data.get("gifs"):
        await update.message.reply_text("❌ اول با `/spem` متن یا با `/add_gif` گیف ذخیره کن.", parse_mode="Markdown")
        return
    if active_tasks.get(chat_id, {}).get("running"):
        await update.message.reply_text("⚠️ قبلاً فعال.")
        return
    active_tasks[chat_id] = {"running": True}
    await update.message.reply_text(f"🚀 شروع شد! {len(data['targets'])} نفر تگ میشن.")
    asyncio.create_task(spam_loop(chat_id, context))

async def cmd_stop_spem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    chat_id = str(update.effective_chat.id)
    if active_tasks.get(chat_id, {}).get("running"):
        active_tasks[chat_id]["running"] = False
        await update.message.reply_text("🛑 متوقف شد.")
    else:
        await update.message.reply_text("چیزی فعال نبود.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ فقط سازنده ربات.")
        return
    data = db.get(SHARED_KEY, {})
    chat_id = str(update.effective_chat.id)
    running = active_tasks.get(chat_id, {}).get("running", False)
    await update.message.reply_text(
        f"📊 تعداد آیدی‌ها: {len(data.get('targets', []))}\n"
        f"تعداد متن‌ها: {len(data.get('messages', []))}\n"
        f"تعداد گیف‌ها: {len(data.get('gifs', []))}\n"
        f"وضعیت در این گروه: {'🟢 فعال' if running else '🔴 خاموش'}",
        parse_mode="Markdown"
    )

# ---------- مدیریت ادمین‌ها ----------
async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ فقط سازنده اصلی ربات.")
        return
    if not context.args:
        await update.message.reply_text("فرمت: `/add_admin 123456789`", parse_mode="Markdown")
        return
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عدد باشه.")
        return
    admins = db.get("allowed_admins", [OWNER_ID])
    if new_admin_id in admins:
        await update.message.reply_text("⚠️ از قبل ادمین هست.")
        return
    admins.append(new_admin_id)
    db["allowed_admins"] = admins
    save_db(db)
    await update.message.reply_text(f"✅ کاربر `{new_admin_id}` ادمین شد.", parse_mode="Markdown")

async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ فقط سازنده اصلی ربات.")
        return
    if not context.args:
        await update.message.reply_text("فرمت: `/remove_admin 123456789`", parse_mode="Markdown")
        return
    try:
        remove_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ آیدی باید عدد باشه.")
        return
    admins = db.get("allowed_admins", [OWNER_ID])
    if remove_id == OWNER_ID:
        await update.message.reply_text("❌ نمی‌تونی خودت رو حذف کنی.")
        return
    if remove_id not in admins:
        await update.message.reply_text("⚠️ این کاربر ادمین نیست.")
        return
    admins.remove(remove_id)
    db["allowed_admins"] = admins
    save_db(db)
    await update.message.reply_text(f"🗑️ کاربر `{remove_id}` حذف شد.", parse_mode="Markdown")

# ---------- راهنما ----------
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **دستورها:**\n"
        "`/id @user` یا `/id 123456789` — ذخیره آیدی\n"
        "`/targets` — نمایش لیست تگ‌ها\n"
        "`/clear_ids` — پاک کردن لیست آیدی‌ها\n"
        "`/spem متن1 | متن2` — ذخیره متن‌ها\n"
        "`/spem_list` — نمایش لیست متن‌ها\n"
        "`/clear_spem` — پاک کردن لیست متن‌ها\n"
        "`/add_gif` — ذخیره گیف جدید\n"
        "`/list_gifs` — نمایش لیست گیف‌ها\n"
        "`/remove_gif <شماره>` — حذف یک گیف خاص\n"
        "`/clear_gifs` — پاک کردن کل لیست گیف‌ها\n"
        "`/set_config 10 3 100 0` — تنظیمات\n"
        "`/start_spem` — شروع\n"
        "`/stop_spem` — توقف\n"
        "`/status` — وضعیت\n"
        "`/add_admin 123456789` — اضافه کردن ادمین\n"
        "`/remove_admin 123456789` — حذف ادمین",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("targets", cmd_targets))
    app.add_handler(CommandHandler("clear_ids", cmd_clear_ids))
    app.add_handler(CommandHandler("spem", cmd_spem))
    app.add_handler(CommandHandler("spem_list", cmd_spem_list))
    app.add_handler(CommandHandler("clear_spem", cmd_clear_spem))
    app.add_handler(CommandHandler("add_gif", cmd_add_gif))
    app.add_handler(CommandHandler("list_gifs", cmd_list_gifs))
    app.add_handler(CommandHandler("remove_gif", cmd_remove_gif))
    app.add_handler(CommandHandler("clear_gifs", cmd_clear_gifs))
    app.add_handler(CommandHandler("set_config", cmd_set_config))
    app.add_handler(CommandHandler("start_spem", cmd_start_spem))
    app.add_handler(CommandHandler("stop_spem", cmd_stop_spem))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("add_admin", cmd_add_admin))
    app.add_handler(CommandHandler("remove_admin", cmd_remove_admin))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.ANIMATION, handle_gif))

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
            except Exception:
                pass

    threading.Thread(target=keep_alive, daemon=True).start()

    print("✅ ربات روشن شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
