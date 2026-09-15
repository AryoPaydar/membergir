from telegram import Update
from telegram.ext import ContextTypes
from database import db
from bot_manager import get_user, is_admin, get_setting
from utils.keyboards import inline
from utils.helpers import format_number

# ==================== منوی پیگیری ====================
async def tracking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 بخش پیگیری سفارشات\n\nگزینه مورد نظر را انتخاب کنید:",
        reply_markup=inline([
            [("📌 سفارشات من", "my_orders")],
            [("🛍 سفارشات در حال اجرا", "my_running_orders")],
            [("❌ لغو سفارش", "cancel_order_menu")],
            [("📜 قوانین", "rules")],
        ])
    )

# ==================== سفارشات من ====================
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    with db.conn() as c:
        orders = c.execute("""
            SELECT o.*, 
                   (SELECT COUNT(*) FROM order_members om WHERE om.order_id = o.id AND om.left_at IS NULL) as active_members
            FROM orders o
            WHERE o.admin_id = ?
            ORDER BY o.id DESC
            LIMIT 20
        """, (user_id,)).fetchall()
    
    if not orders:
        await q.message.reply_text(
            "📭 هنوز سفارشی ثبت نکرده‌اید.",
            reply_markup=inline([[("🔙 بازگشت", "tracking_back")]])
        )
        return
    
    text = "📋 <b>سفارشات اخیر شما:</b>\n\n"
    for o in orders:
        status_emoji = {
            "running": "♻️",
            "completed": "✅",
            "cancelled": "❌",
        }.get(o["status"], "❓")
        
        text += (
            f"{status_emoji} <b>سفارش #{o['id']}</b>\n"
            f"📢 کانال: @{o['channel']}\n"
            f"👥 ممبر: {o['member_received']}/{o['member_target']}\n"
            f"💰 هزینه: {o['coins_cost']:,} سکه\n"
            f"📆 تاریخ: {o['created_at']}\n"
            f"——————\n"
        )
    
    rows = []
    for o in orders[:10]:
        rows.append([(f"#{o['id']} - @{o['channel']}", f"order_detail:{o['id']}")])
    rows.append([("🔙 بازگشت", "tracking_back")])
    
    await q.message.reply_text(text, parse_mode="HTML", reply_markup=inline(rows))

# ==================== جزئیات سفارش ====================
async def order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        order = c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            await q.message.reply_text("❌ سفارش یافت نشد.")
            return
        order = dict(order)
        
        # فقط صاحب سفارش یا ادمین
        if order["admin_id"] != user_id and not is_admin(user_id):
            await q.message.reply_text("❌ دسترسی ندارید.")
            return
        
        # اعضای فعال
        active = c.execute(
            "SELECT COUNT(*) c FROM order_members WHERE order_id=? AND left_at IS NULL",
            (order_id,)
        ).fetchone()["c"]
        
        left = c.execute(
            "SELECT COUNT(*) c FROM order_members WHERE order_id=? AND left_at IS NOT NULL",
            (order_id,)
        ).fetchone()["c"]
    
    status_text = {
        "running": "♻️ در حال اجرا",
        "completed": "✅ تکمیل شده",
        "cancelled": "❌ لغو شده",
    }.get(order["status"], "❓")
    
    text = (
        f"📋 <b>جزئیات سفارش #{order_id}</b>\n\n"
        f"📢 کانال: @{order['channel']}\n"
        f"👥 ممبر درخواستی: {order['member_target']}\n"
        f"✅ ممبر دریافتی: {order['member_received']}\n"
        f"🟢 اعضای فعال: {active}\n"
        f"🔴 اعضای ترک‌کرده: {left}\n"
        f"💰 هزینه: {order['coins_cost']:,} سکه\n"
        f"📆 تاریخ ثبت: {order['created_at']}\n"
        f"📊 وضعیت: {status_text}\n"
    )
    
    rows = []
    if order["status"] == "running":
        if get_setting("cancel_enabled", "on") == "on":
            rows.append([("❌ لغو سفارش", f"cancel_confirm:{order_id}")])
    rows.append([("🔙 بازگشت", "my_orders")])
    
    await q.message.reply_text(text, parse_mode="HTML", reply_markup=inline(rows))

# ==================== سفارشات در حال اجرا ====================
async def my_running_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    with db.conn() as c:
        orders = c.execute("""
            SELECT * FROM orders
            WHERE admin_id = ? AND status = 'running'
            ORDER BY id DESC
        """, (user_id,)).fetchall()
    
    if not orders:
        await q.message.reply_text(
            "📭 سفارش در حال اجرایی ندارید.",
            reply_markup=inline([[("🔙 بازگشت", "tracking_back")]])
        )
        return
    
    text = "🛍 <b>سفارشات در حال اجرا:</b>\n\n"
    for o in orders:
        remaining = o["member_target"] - o["member_received"]
        text += (
            f"♻️ <b>#{o['id']}</b> - @{o['channel']}\n"
            f"👥 باقی‌مانده: {remaining}/{o['member_target']}\n"
            f"——————\n"
        )
    
    rows = [[(f"#{o['id']}", f"order_detail:{o['id']}")] for o in orders[:10]]
    rows.append([("🔙 بازگشت", "tracking_back")])
    await q.message.reply_text(text, parse_mode="HTML", reply_markup=inline(rows))

# ==================== لغو سفارش ====================
async def cancel_order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    if get_setting("cancel_enabled", "on") != "on":
        await q.message.reply_text("❌ لغو سفارش غیرفعال است.")
        return
    
    min_members = int(get_setting("cancel_min_members", "100"))
    
    with db.conn() as c:
        orders = c.execute("""
            SELECT * FROM orders
            WHERE admin_id = ? AND status = 'running' AND member_target >= ?
            ORDER BY id DESC
        """, (user_id, min_members)).fetchall()
    
    if not orders:
        await q.message.reply_text(
            f"❌ سفارشی برای لغو یافت نشد.\n\n"
            f"👈 حداقل ممبر برای لغو: {min_members}",
            reply_markup=inline([[("🔙 بازگشت", "tracking_back")]])
        )
        return
    
    rows = [[(f"#{o['id']} - @{o['channel']}", f"cancel_confirm:{o['id']}")] for o in orders[:10]]
    rows.append([("🔙 بازگشت", "tracking_back")])
    await q.message.reply_text("❌ سفارش مورد نظر برای لغو:", reply_markup=inline(rows))

async def cancel_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        order = c.execute("SELECT * FROM orders WHERE id=? AND admin_id=?", (order_id, user_id)).fetchone()
    if not order:
        await q.message.reply_text("❌ سفارش یافت نشد.")
        return
    
    order = dict(order)
    if order["status"] != "running":
        await q.message.reply_text("❌ این سفارش فعال نیست.")
        return
    
    if get_setting("cancel_enabled", "on") != "on":
        await q.message.reply_text("❌ لغو سفارش غیرفعال است.")
        return
    
    # چک زمان انتظار
    from utils.helpers import now_ts
    cancel_at = order.get("cancel_at") or 0
    if now_ts() < cancel_at:
        remaining = cancel_at - now_ts()
        await q.answer(f"⏳ {remaining} ثانیه دیگر می‌توانید لغو کنید.", show_alert=True)
        return
    
    # محاسبه بازگشت
    ratio = float(get_setting("cancel_refund_ratio", "0.5"))
    remaining = order["member_target"] - order["member_received"]
    refund = int(remaining * ratio)
    
    await q.message.reply_text(
        f"⁉️ آیا از لغو سفارش <b>#{order_id}</b> مطمئن هستید؟\n\n"
        f"👥 ممبر باقی‌مانده: {remaining}\n"
        f"💰 سکه بازگشتی: {refund:,}",
        parse_mode="HTML",
        reply_markup=inline([
            [("✅ بله، لغو کن", f"cancel_do:{order_id}"),
             ("❌ خیر", "tracking_back")],
        ])
    )

async def cancel_order_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        order = c.execute("SELECT * FROM orders WHERE id=? AND admin_id=?", (order_id, user_id)).fetchone()
        if not order:
            await q.answer("❌ یافت نشد.", show_alert=True)
            return
        order = dict(order)
        if order["status"] != "running":
            await q.answer("❌ قبلاً بسته شده.", show_alert=True)
            return
        
        ratio = float(get_setting("cancel_refund_ratio", "0.5"))
        remaining = order["member_target"] - order["member_received"]
        refund = int(remaining * ratio)
        
        # بستن سفارش + بازگشت سکه — اتمیک
        c.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
        c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (refund, user_id))
        c.execute("""
            INSERT INTO transactions (to_id, amount, type, description)
            VALUES (?, ?, 'order_cancel_refund', ?)
        """, (user_id, refund, f"بازگشت از سفارش #{order_id}"))
    
    # حذف پست از کانال
    try:
        from config import Config
        await context.bot.delete_message(f"@{Config.ADS_CHANNEL}", order["post_id"])
    except Exception:
        pass
    
    await q.answer(f"✅ سفارش لغو شد. {refund:,} سکه بازگشت.", show_alert=True)
    try:
        await q.message.delete()
    except Exception:
        pass
    
    from utils.keyboards import main_menu
    await context.bot.send_message(
        user_id,
        f"✅ سفارش #{order_id} با موفقیت لغو شد.\n"
        f"💰 {refund:,} سکه به حساب شما بازگشت.",
        reply_markup=main_menu(is_admin(user_id))
    )

# ==================== قوانین ====================
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = get_setting("rules_text",
        "📜 <b>قوانین ربات:</b>\n\n"
        "۱. استفاده از ربات به معنی پذیرش قوانین است.\n"
        "۲. هرگونه تخلف منجر به مسدودیت می‌شود.\n"
        "۳. مسئولیت اطلاعات وارد شده بر عهده کاربر است."
    )
    await q.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "tracking_back")]])
    )

async def tracking_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    
    from utils.keyboards import main_menu
    await context.bot.send_message(
        q.from_user.id,
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(q.from_user.id))
    )

# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    
    handlers = {
        "my_orders": my_orders,
        "my_running_orders": my_running_orders,
        "cancel_order_menu": cancel_order_menu,
        "rules": rules,
        "tracking_back": tracking_back,
    }
    if data in handlers:
        await handlers[data](update, context)
        return True
    if data.startswith("order_detail:"):
        await order_detail(update, context)
        return True
    if data.startswith("cancel_confirm:"):
        await cancel_order_confirm(update, context)
        return True
    if data.startswith("cancel_do:"):
        await cancel_order_do(update, context)
        return True
    return False

# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    این ماژول state ندارد — همه کارها با callback انجام میشود.
    این تابع برای یکپارچگی با main.py تعریف شده است.
    """
    return False