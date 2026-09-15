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
from handlers import admin_shop, admin_texts

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
    with __import__("database").db.conn() as c:
        total = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        banned = c.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
        orders = c.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        running = c.execute("SELECT COUNT(*) c FROM orders WHERE status='running'").fetchone()["c"]
    
    text = (
        f"📈 <b>آمار ربات</b>\n\n"
        f"👥 کل کاربران: {total:,}\n"
        f"⛔️ بن‌شده: {banned:,}\n"
        f"📌 کل سفارشات: {orders:,}\n"
        f"🔄 در حال اجرا: {running:,}\n"
        f"💰 موجودی فروشگاه: {format_number(get_setting('shop_balance', '0'))} ریال"
    )
    await update.message.reply_text(text, parse_mode="HTML")

# ==================== ارسال پیام همگانی ====================
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "📨 نوع ارسال را انتخاب کنید:",
        reply_markup=inline([
            [("📝 پیام همگانی", "bc_text"), ("🔁 فوروارد همگانی", "bc_fwd")],
            [("👤 پیام به یک کاربر", "bc_one")],
        ])
    )

async def broadcast_run(update: Update, context: ContextTypes.DEFAULT_TYPE, fwd: bool = False):
    if not is_admin(update.effective_user.id):
        return
    from bot_manager import set_user_state
    set_user_state(update.effective_user.id, "broadcast_fwd" if fwd else "broadcast_text")
    await update.message.reply_text("📌 پیام خود را ارسال کنید.", reply_markup=back_button())

async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, fwd: bool):
    """ارسال همگانی"""
    from database import db
    from bot_manager import set_user_state
    msg = update.message
    with db.conn() as c:
        rows = c.execute("SELECT user_id FROM users WHERE banned = 0").fetchall()
    
    sent = failed = 0
    for r in rows:
        try:
            if fwd:
                await msg.forward(r["user_id"])
            else:
                await msg.copy(r["user_id"])
            sent += 1
        except Exception:
            failed += 1
    
    set_user_state(update.effective_user.id, "none")
    await msg.reply_text(
        f"✅ ارسال شد.\n✔️ موفق: {sent}\n❌ ناموفق: {failed}",
        reply_markup=admin_panel()
    )

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
    """پردازش state ادمین — True اگه هندل شد"""
    user = update.effective_user
    if not is_admin(user.id):
        return False
    from bot_manager import get_user_state, set_user_state
    state, data = get_user_state(user.id)
    if state == "none" or not state:
        return False
    
    msg = update.message
    text = (msg.text or "").strip()
    
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
    
    if state == "broadcast_text":
        await do_broadcast(update, context, fwd=False)
        return True
    
    if state == "broadcast_fwd":
        await do_broadcast(update, context, fwd=True)
        return True
    
    return False

# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    user = q.from_user
    
    if not is_admin(user.id):
        return False
    
    if data == "bc_text":
        await q.answer()
        await broadcast_run(update, context, fwd=False)
        return True
    if data == "bc_fwd":
        await q.answer()
        await broadcast_run(update, context, fwd=True)
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

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    text = (update.message.text or "").strip()
    if text == "👑 پنل مدیریت":
        await admin_panel_handler(update, context)
        return True
    if is_admin(update.effective_user.id) and text in ADMIN_BUTTONS:
        await ADMIN_BUTTONS[text](update, context)
        return True
    return False
