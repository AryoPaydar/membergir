from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from bot_manager import (
    is_admin, is_main_admin, add_admin, remove_admin, list_admins,
    get_user, update_user, add_warning, ban_user, unban_user,
    set_setting, get_setting, set_bot_power, is_bot_on
)
from utils.keyboards import admin_panel, main_menu, back_button, inline
from utils.helpers import is_positive_int, is_valid_username, format_number, now_ts
from database import db
from datetime import datetime
import math
import json

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text(
        "👑 پنل مدیریت",
        reply_markup=admin_panel()
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    await update.message.reply_text(
        "🏠 منوی اصلی",
        reply_markup=main_menu(True)
    )

# ==================== آمار ====================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    with db.conn() as c:
        # کاربران
        total = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        banned = c.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
        warned = c.execute("SELECT COUNT(*) c FROM users WHERE warnings > 0").fetchone()["c"]
        
        # سفارشات
        orders = c.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        running = c.execute("SELECT COUNT(*) c FROM orders WHERE status='running'").fetchone()["c"]
        
        # کانال‌ها و گروه‌ها
        channels = c.execute(
            "SELECT COUNT(*) c FROM bot_chats WHERE chat_type = 'channel'"
        ).fetchone()["c"]
        groups = c.execute(
            "SELECT COUNT(*) c FROM bot_chats WHERE chat_type IN ('group', 'supergroup')"
        ).fetchone()["c"]
    
    text = (
        f"📈 <b>آمار ربات</b>\n\n"
        f"کل کانال ها : {channels:,}\n"
        f"کل گروه ها : {groups:,}\n"
        f"👥 کل کاربران: {total:,}\n"
        f"⛔️ کاربران بن‌شده: {banned:,}\n"
        f"کاربران دارای اخطار : {warned:,}\n"
        f"📌 کل سفارشات: {orders:,}\n"
        f"🔄 سفارشات در حال اجرا: {running:,}"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ==================== ارسال پیام ====================
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "📨 نوع ارسال را انتخاب کنید:",
        reply_markup=inline([
            [("📤 ارسال در ربات", "bc_to_bot"), ("📢 ارسال در کانال", "bc_to_channel")],
            [("👤 ارسال به کاربر خاص", "bc_to_user"), ("📌 ارسال در کانال خاص", "bc_to_specific_channel")],
            [("🔙 بازگشت به پنل مدیریت", "bc_back_panel")],
        ])
    )

async def bc_back_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    from bot_manager import set_user_state
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())

# === ارسال در ربات ===
async def bc_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        "به چه کسانی می‌خواهید پیام ارسال کنید؟",
        reply_markup=inline([
            [("👥 همه کاربران", "bc_bot:all:0")],
            [("🟢 کاربران فعال در 3 روز گذشته", "bc_bot:active3:0")],
            [("🔴 کاربران غیرفعال در 3 روز گذشته", "bc_bot:inactive3:0")],
            [("🔴 کاربران غیرفعال در 7 روز گذشته", "bc_bot:inactive7:0")],
            [("🔙 بازگشت به پنل مدیریت", "bc_back_panel")],
        ])
    )

async def bc_bot_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    _, target, _ = q.data.split(":")
    from bot_manager import set_user_state
    set_user_state(user_id, "bc_text", {"mode": "bot", "target": target})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        user_id,
        "لطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )

# === ارسال در کانال ===
async def bc_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    from bot_manager import set_user_state
    set_user_state(user_id, "bc_text", {"mode": "channel_all"})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        user_id,
        "لطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )

# === ارسال به کاربر خاص ===
async def bc_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    from bot_manager import set_user_state
    set_user_state(user_id, "bc_search_user")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        user_id,
        "نام کاربری، یوزرنیم یا شناسه کاربری فرد مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )

# === ارسال در کانال خاص ===
async def bc_to_specific_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    from bot_manager import set_user_state
    set_user_state(user_id, "bc_search_channel")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        user_id,
        "نام کانال، ایدی کانال یا شناسه عددی کانال مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )

# ==================== جستجوی کاربر ====================
def user_search_result_text(users, page):
    per_page = 10
    start = page * per_page
    chunk = users[start:start+per_page]
    txt = f"{len(users)} کاربر یافت شد:\n\n"
    for i, u in enumerate(chunk, start+1):
        name = u["first_name"] or "کاربر"
        username = f"@{u['username']}" if u["username"] else "ندارد"
        txt += (
            f"{i}. نام کاربری : {name}\n"
            f"🆔 یوزرنیم : {username}\n"
            f"🔰 شماره کاربری : {u['user_id']}\n\n"
        )
    return txt, chunk

def user_search_kb(users, page):
    per_page = 10
    total_pages = math.ceil(len(users) / per_page)
    start = page * per_page
    chunk = users[start:start+per_page]
    rows = []
    for u in chunk:
        name = (u["first_name"] or "کاربر")[:20]
        rows.append([(f"📤 ارسال به {name}", f"bc_user_pick:{u['user_id']}")])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"bc_user_page:{page-1}"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"bc_user_page:{page+1}"))
        rows.append(nav)
    rows.append([("🔙 بازگشت به پنل مدیریت", "bc_back_panel")])
    return rows

async def do_user_search(update, query):
    query_clean = query.strip().lstrip("@")
    with db.conn() as c:
        if query_clean.isdigit():
            users = c.execute(
                "SELECT user_id, first_name, username FROM users WHERE user_id = ?",
                (int(query_clean),)
            ).fetchall()
        else:
            users = c.execute(
                "SELECT user_id, first_name, username FROM users WHERE username LIKE ? OR first_name LIKE ?",
                (f"%{query_clean}%", f"%{query}%")
            ).fetchall()
    return users

async def handle_bc_user_search(update, context, text):
    users = await do_user_search(update, text)
    if not users:
        await update.message.reply_text(
            "کاربری با مشخصات ارسالی یافت نشد\nلطفا دوباره ارسال فرمایید:",
            reply_markup=back_button()
        )
        return
    from bot_manager import set_user_state
    set_user_state(update.effective_user.id, "bc_search_user", {"last_query": text})
    txt, _ = user_search_result_text(users, 0)
    kb = user_search_kb(users, 0)
    await update.message.reply_text(txt, reply_markup=inline(kb))

# ==================== جستجوی کانال ====================
def channel_search_result_text(channels, page):
    per_page = 10
    start = page * per_page
    chunk = channels[start:start+per_page]
    txt = f"{len(channels)} کانال یافت شد:\n\n"
    for i, ch in enumerate(chunk, start+1):
        title = ch["title"] or "بدون نام"
        username = f"@{ch['username']}" if ch["username"] else "ندارد"
        cid = ch["chat_id"]
        txt += (
            f"{i}. نام کانال: {title}\n"
            f"🆔 یوزرنیم : {username}\n"
            f"🔰 شناسه عددی : {cid}\n\n"
        )
    return txt, chunk

def channel_search_kb(channels, page):
    per_page = 10
    total_pages = math.ceil(len(channels) / per_page)
    start = page * per_page
    chunk = channels[start:start+per_page]
    rows = []
    for ch in chunk:
        title = (ch["title"] or "کانال")[:20]
        cid = ch["chat_id"]
        rows.append([(f"📤 ارسال به {title}", f"bc_channel_pick:{cid}")])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"bc_channel_page:{page-1}"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"bc_channel_page:{page+1}"))
        rows.append(nav)
    rows.append([("🔙 بازگشت به پنل مدیریت", "bc_back_panel")])
    return rows

async def handle_bc_channel_search(update, context, text):
    qc = text.strip().lstrip("@")
    with db.conn() as c:
        if qc.lstrip("-").isdigit():
            channels = c.execute(
                "SELECT chat_id, title, username FROM bot_chats WHERE chat_id = ? LIMIT 50",
                (int(qc),)
            ).fetchall()
        else:
            channels = c.execute(
                "SELECT chat_id, title, username FROM bot_chats WHERE title LIKE ? OR username LIKE ? LIMIT 50",
                (f"%{qc}%", f"%{qc}%")
            ).fetchall()
    if not channels:
        await update.message.reply_text(
            "کانالی با مشخصات ارسالی یافت نشد\nلطفا دوباره ارسال فرمایید:",
            reply_markup=back_button()
        )
        return
    from bot_manager import set_user_state
    set_user_state(update.effective_user.id, "bc_search_channel", {"last_query": text})
    txt, _ = channel_search_result_text(channels, 0)
    kb = channel_search_kb(channels, 0)
    await update.message.reply_text(txt, reply_markup=inline(kb))

# ==================== انتخاب کاربر/کانال ====================
async def bc_user_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = int(q.data.split(":")[1])
    with db.conn() as c:
        u = c.execute("SELECT first_name FROM users WHERE user_id = ?", (uid,)).fetchone()
    name = u["first_name"] if u else "کاربر"
    from bot_manager import set_user_state
    set_user_state(q.from_user.id, "bc_text", {"mode": "specific_user", "target_id": uid})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        f"شما در حال ارسال پیام به {name} هستید\nلطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )

async def bc_channel_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.data.split(":", 1)[1]
    from bot_manager import set_user_state
    set_user_state(q.from_user.id, "bc_text", {"mode": "specific_channel", "target_id": cid})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        f"شما در حال ارسال پیام در کانال هستید\nلطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )

# ==================== تأیید ارسال ====================
async def bc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    from bot_manager import get_user_state, set_user_state
    state, data = get_user_state(user_id)
    if state != "bc_confirm":
        return
    text = data.get("text", "")
    mode = data.get("mode", "")
    target = data.get("target")
    target_id = data.get("target_id")
    try:
        await q.message.delete()
    except Exception:
        pass
    sent = 0
    failed = 0
    if mode == "bot":
        now_ts_val = int(datetime.now().timestamp())
        with db.conn() as c:
            if target == "all":
                rows = c.execute("SELECT user_id FROM users WHERE banned = 0").fetchall()
            elif target == "active3":
                rows = c.execute(
                    "SELECT user_id FROM users WHERE banned = 0 AND last_daily >= ?",
                    (now_ts_val - 3*86400,)
                ).fetchall()
            elif target == "inactive3":
                rows = c.execute(
                    "SELECT user_id FROM users WHERE banned = 0 AND (last_daily < ? OR last_daily = 0)",
                    (now_ts_val - 3*86400,)
                ).fetchall()
            elif target == "inactive7":
                rows = c.execute(
                    "SELECT user_id FROM users WHERE banned = 0 AND (last_daily < ? OR last_daily = 0)",
                    (now_ts_val - 7*86400,)
                ).fetchall()
            else:
                rows = []
        for r in rows:
            try:
                await context.bot.send_message(r["user_id"], text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        set_user_state(user_id, "none")
        await context.bot.send_message(
            user_id,
            f"✅ ارسال شد.\n✔️ موفق: {sent}\n❌ ناموفق: {failed}",
            reply_markup=admin_panel()
        )
        return
    elif mode == "channel_all":
        with db.conn() as c:
            chs = c.execute(
                "SELECT chat_id, title, username FROM bot_chats"
            ).fetchall()
        
        success_chats = []
        failed_chats = []
        
        for ch in chs:
            cid = ch["chat_id"]
            info = {"chat_id": cid, "title": ch["title"], "username": ch["username"]}
            try:
                await context.bot.send_message(cid, text, parse_mode="HTML")
                sent += 1
                success_chats.append(info)
            except Exception:
                failed += 1
                failed_chats.append(info)
        
        # ذخیره لیست در state_data برای دکمه‌های شیشه‌ای
        set_user_state(user_id, "bc_result", {
            "success": success_chats,
            "failed": failed_chats,
            "sent": sent,
            "failed_count": failed,
        })
        
        rows = [
            [("✅ مشاهده کانال‌های موفق", "bc_show_success:0"),
             ("❌ مشاهده کانال‌های ناموفق", "bc_show_failed:0")],
            [("🔙 بازگشت به پنل مدیریت", "bc_back_panel")],
        ]
        
        await context.bot.send_message(
            user_id,
            f"پیام شما ارسال شد.\n"
            f"🔍 تعداد کانال/گروه‌های شناسایی‌شده: {len(chs)}\n\n"
            f"✔️ موفق: {sent}\n"
            f"❌ ناموفق: {failed}",
            reply_markup=inline(rows)
        )
        return
    elif mode == "specific_channel":
        if target_id:
            try:
                await context.bot.send_message(int(target_id), text, parse_mode="HTML")
                sent += 1
            except Exception as e:
                failed += 1
                await context.bot.send_message(user_id, f"❌ خطا: {e}")
    elif mode == "specific_user":
        if target_id:
            try:
                await context.bot.send_message(int(target_id), text, parse_mode="HTML")
                sent += 1
            except Exception as e:
                failed += 1
                await context.bot.send_message(user_id, f"❌ خطا: {e}")
    set_user_state(user_id, "none")
    await context.bot.send_message(
        user_id,
        f"✅ ارسال شد.\n✔️ موفق: {sent}\n❌ ناموفق: {failed}",
        reply_markup=admin_panel()
    )

async def bc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("لغو شد.")
    from bot_manager import set_user_state
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())

# ==================== نمایش لیست موفق/ناموفق ====================
def _format_chat_list(chats, page):
    per_page = 10
    start = page * per_page
    chunk = chats[start:start+per_page]
    txt = f"{len(chats)} کانال یافت شد:\n\n"
    for i, ch in enumerate(chunk, start+1):
        title = ch.get("title") or "بدون نام"
        username = f"@{ch['username']}" if ch.get("username") else "ندارد"
        cid = ch.get("chat_id")
        txt += (
            f"{i}. نام کانال: {title}\n"
            f"🆔 یوزرنیم : {username}\n"
            f"🔰 شناسه عددی : {cid}\n\n"
        )
    return txt

def _chat_list_kb(chats, page, kind):
    per_page = 10
    total_pages = math.ceil(len(chats) / per_page) if chats else 0
    rows = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"bc_show_{kind}:{page-1}"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"bc_show_{kind}:{page+1}"))
        rows.append(nav)
    rows.append([("🔙 بازگشت به پنل مدیریت", "bc_back_panel")])
    return rows

async def bc_show_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    from bot_manager import get_user_state
    state, data = get_user_state(user_id)
    if state != "bc_result":
        await q.answer("اطلاعات منقضی شده.", show_alert=True)
        return
    page = int(q.data.split(":")[1])
    chats = data.get("success", [])
    if not chats:
        await q.message.edit_text(
            "❌ هیچ کانال موفقی وجود ندارد.",
            reply_markup=inline([[("🔙 بازگشت به پنل مدیریت", "bc_back_panel")]])
        )
        return
    txt = _format_chat_list(chats, page)
    kb = _chat_list_kb(chats, page, "success")
    try:
        await q.message.edit_text(txt, reply_markup=inline(kb))
    except Exception:
        pass

async def bc_show_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    from bot_manager import get_user_state
    state, data = get_user_state(user_id)
    if state != "bc_result":
        await q.answer("اطلاعات منقضی شده.", show_alert=True)
        return
    page = int(q.data.split(":")[1])
    chats = data.get("failed", [])
    if not chats:
        await q.message.edit_text(
            "✅ هیچ کانال ناموفقی وجود ندارد.",
            reply_markup=inline([[("🔙 بازگشت به پنل مدیریت", "bc_back_panel")]])
        )
        return
    txt = _format_chat_list(chats, page)
    kb = _chat_list_kb(chats, page, "failed")
    try:
        await q.message.edit_text(txt, reply_markup=inline(kb))
    except Exception:
        pass

# ==================== ادمین‌ها ====================
async def admins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    rows = [[("📜 لیست مدیران", "admins_list")]]
    if is_main_admin(update.effective_user.id):
        rows.append([("➕ افزودن", "admins_add"), ("➖ حذف", "admins_remove")])
    await update.message.reply_text("👤 مدیریت ادمین‌ها:", reply_markup=inline(rows))

async def admins_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    admins = list_admins()
    text = "📜 لیست مدیران:\n\n" + "\n".join(f"• <a href='tg://user?id={a}'>{a}</a>" for a in admins)
    await q.message.reply_text(text, parse_mode="HTML")

# ==================== آیدی‌یاب ====================
async def id_finder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    from bot_manager import set_user_state
    set_user_state(update.effective_user.id, "admin_search_id")
    await update.message.reply_text("🆔 آیدی عددی کاربر را وارد کنید:", reply_markup=back_button())

# ==================== اخطار ====================
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    from bot_manager import set_user_state
    set_user_state(update.effective_user.id, "admin_warn")
    await update.message.reply_text("🆔 آیدی کاربر را وارد کنید:", reply_markup=back_button())

# ==================== خاموش/روشن ====================
async def power_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    on = is_bot_on()
    await update.message.reply_text(
        f"🔌 وضعیت فعلی: {'روشن ✅' if on else 'خاموش ❌'}",
        reply_markup=inline([
            [(("🔕 خاموش کن" if on else "🔔 روشن کن"), "toggle_power")],
            [("📝 تنظیم متن خاموشی", "set_power_text")],
        ])
    )

# ==================== روتر وضعیت ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not is_admin(user.id):
        return False
    from bot_manager import get_user_state, set_user_state
    state, data = get_user_state(user.id)
    if not state or state == "none":
        return False
    msg = update.message
    text = (msg.text or "").strip()

    if text in ("🔙 بازگشت", "🔙 بازگشت به پنل مدیریت", "بازگشت به پنل مدیریت"):
        set_user_state(user.id, "none")
        await msg.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True

    if state == "admin_search_id":
        if text == "🔙 بازگشت":
            set_user_state(user.id, "none")
            await msg.reply_text("🏠", reply_markup=admin_panel())
            return True
        if is_positive_int(text):
            u = get_user(int(text))
            if u:
                await msg.reply_text(f"👤 <a href='tg://user?id={u['user_id']}'>کاربر {u['user_id']}</a>", parse_mode="HTML")
            else:
                await msg.reply_text("❌ کاربر یافت نشد.")
            set_user_state(user.id, "none")
            return True
    if state == "admin_warn":
        if text == "🔙 بازگشت":
            set_user_state(user.id, "none")
            await msg.reply_text("🏠", reply_markup=admin_panel())
            return True
        if is_positive_int(text):
            target = int(text)
            u = get_user(target)
            if u:
                new_count = add_warning(target)
                await msg.reply_text(f"⚠️ اخطار ثبت شد. تعداد اخطار: {new_count}")
                try:
                    await context.bot.send_message(
                        target,
                        f"⚠️ شما یک اخطار دریافت کردید.\nتعداد اخطار: {new_count} از {Config.MAX_WARNINGS}"
                    )
                except Exception:
                    pass
            else:
                await msg.reply_text("❌ کاربر یافت نشد.")
            set_user_state(user.id, "none")
            return True
    if state == "bc_text":
        set_user_state(user.id, "bc_confirm", {**data, "text": text})
        await msg.reply_text(
            "آیا از ارسال پیام خود مطمئن هستید ؟",
            reply_markup=inline([
                [("✅ بله", "bc_confirm_yes"), ("❌ خیر", "bc_confirm_no")],
            ])
        )
        return True
    if state == "bc_search_user":
        await handle_bc_user_search(update, context, text)
        return True
    if state == "bc_search_channel":
        await handle_bc_channel_search(update, context, text)
        return True
    return False

# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    user = q.from_user
    if not is_admin(user.id):
        return False
    if data == "bc_to_bot":
        await bc_to_bot(update, context)
        return True
    if data.startswith("bc_bot:"):
        await bc_bot_target(update, context)
        return True
    if data == "bc_to_channel":
        await bc_to_channel(update, context)
        return True
    if data == "bc_to_user":
        await bc_to_user(update, context)
        return True
    if data == "bc_to_specific_channel":
        await bc_to_specific_channel(update, context)
        return True
    if data == "bc_back_panel":
        await bc_back_panel(update, context)
        return True
    if data == "bc_confirm_yes":
        await bc_confirm(update, context)
        return True
    if data == "bc_confirm_no":
        await bc_cancel(update, context)
        return True
    if data.startswith("bc_show_success:"):
        await bc_show_success(update, context)
        return True
    if data.startswith("bc_show_failed:"):
        await bc_show_failed(update, context)
        return True
    if data.startswith("bc_user_pick:"):
        await bc_user_pick(update, context)
        return True
    if data.startswith("bc_channel_pick:"):
        await bc_channel_pick(update, context)
        return True
    if data.startswith("bc_user_page:"):
        await q.answer()
        page = int(data.split(":")[1])
        from bot_manager import get_user_state
        state, sdata = get_user_state(user.id)
        query = sdata.get("last_query", "")
        if not query:
            await q.answer("دوباره جستجو کنید.", show_alert=True)
            return True
        users = await do_user_search(update, query)
        if not users:
            return True
        txt, _ = user_search_result_text(users, page)
        kb = user_search_kb(users, page)
        try:
            await q.message.edit_text(txt, reply_markup=inline(kb))
        except Exception:
            pass
        return True
    if data.startswith("bc_channel_page:"):
        await q.answer()
        page = int(data.split(":")[1])
        from bot_manager import get_user_state
        state, sdata = get_user_state(user.id)
        query = sdata.get("last_query", "")
        if not query:
            await q.answer("دوباره جستجو کنید.", show_alert=True)
            return True
        qc = query.strip().lstrip("@")
        with db.conn() as c:
            if qc.lstrip("-").isdigit():
                channels = c.execute(
                    "SELECT chat_id, title, username FROM bot_chats WHERE chat_id = ? LIMIT 50",
                    (int(qc),)
                ).fetchall()
            else:
                channels = c.execute(
                    "SELECT chat_id, title, username FROM bot_chats WHERE title LIKE ? OR username LIKE ? LIMIT 50",
                    (f"%{qc}%", f"%{qc}%")
                ).fetchall()
        if not channels:
            return True
        txt, _ = channel_search_result_text(channels, page)
        kb = channel_search_kb(channels, page)
        try:
            await q.message.edit_text(txt, reply_markup=inline(kb))
        except Exception:
            pass
        return True
    if data == "admins_list":
        await admins_list_cb(update, context)
        return True
    if data == "toggle_power":
        await q.answer()
        set_bot_power(not is_bot_on())
        await power_menu(update, context)
        return True
    if data == "set_power_text":
        await q.answer()
        from bot_manager import set_user_state
        set_user_state(user.id, "set_power_text")
        await q.message.reply_text("📝 متن خاموشی را ارسال کنید:")
        return True
    return False

# ==================== روتر متن (دکمه‌ها) ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    from handlers import admin_shop, admin_texts
    
    text = (update.message.text or "").strip()
    if text == "👑 پنل مدیریت":
        await admin_panel_handler(update, context)
        return True
    
    if not is_admin(update.effective_user.id):
        return False
    
    ADMIN_BUTTONS = {
        "📈 آمار ربات": stats,
        "📨 ارسال پیام": broadcast_start,
        "👤 ادمین‌ها": admins_menu,
        "🆔 آیدی‌یاب": id_finder,
        "⚠️ اخطاردهی": warn_user,
        "🔕 خاموش/روشن": power_menu,
        "🔙 بازگشت به منو": back_to_main,
        "🛍 مدیریت فروشگاه": admin_shop.shop_admin_menu,
        "📇 تنظیم متن‌ها": admin_texts.texts_menu,
    }
    
    if text in ADMIN_BUTTONS:
        await ADMIN_BUTTONS[text](update, context)
        return True
    return False
