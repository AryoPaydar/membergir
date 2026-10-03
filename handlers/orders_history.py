from telegram import Update, LinkPreviewOptions
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import get_user, is_admin, get_setting
from utils.keyboards import inline, main_menu
from utils.helpers import format_number, now_ts
from datetime import datetime
import jdatetime
import math


# ==================== منوی پیگیری ====================
async def tracking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    with db.conn() as c:
        orders = c.execute("""
            SELECT o.*,
                   (SELECT COUNT(*) FROM order_members om
                    WHERE om.order_id = o.id AND om.left_at IS NULL) as active_members,
                   (SELECT COUNT(*) FROM order_members om
                    WHERE om.order_id = o.id AND om.left_at IS NOT NULL) as left_members
            FROM orders o
            WHERE o.admin_id = ? AND o.status = 'running'
            ORDER BY o.post_id ASC
        """, (user_id,)).fetchall()

    if not orders:
        await update.message.reply_text(
            "📭 هنوز سفارش فعالی ثبت نکرده‌اید.",
            reply_markup=main_menu(is_admin(user_id))
        )
        return

    orders = [dict(o) for o in orders]
    await _show_orders_page(update, context, orders, 0, is_first=True)


async def _show_orders_page(update, context, orders, page, is_first=False):
    per_page = 5
    total = len(orders)
    total_pages = math.ceil(total / per_page)
    start = page * per_page
    chunk = orders[start:start + per_page]

    text = "📋 سفارشات اخیر شما:\n\n"

    for o in chunk:
        post_id = o.get("post_id") or o["id"]
        channel = o["channel"]
        post_link = f"https://t.me/{Config.ADS_CHANNEL}/{post_id}"

        try:
            dt = datetime.strptime(str(o["created_at"])[:19], "%Y-%m-%d %H:%M:%S")
            date_jalali = jdatetime.datetime.fromgregorian(datetime=dt).strftime("%Y/%m/%d %H:%M")
        except Exception:
            date_jalali = str(o["created_at"])[:16]

        status_text = {
            "running": "در حال اجرا ♻️",
            "completed": "تکمیل شده ✅",
            "cancelled": "لغو شده ❌",
        }.get(o["status"], "❓")

        text += (
            f"<a href='{post_link}'>💮 سفارش شماره #{post_id}</a>\n"
            f"\n"
            f"📢 کانال: @{channel}\n"
            f"👥 ممبر درخواستی: {o['member_target']:,}\n"
            f"🟢 ممبر دریافتی: {o['member_received']:,}\n"
            f"🔴 اعضای ترک‌کرده: {o['left_members']:,}\n"
            f"📆 تاریخ ثبت: {date_jalali}\n"
            f"📊 وضعیت: {status_text}\n"
            f"————————————\n"
        )

    rows = []
    cancel_buttons = []
    for o in chunk:
        post_id = o.get("post_id") or o["id"]
        if o["status"] == "running":
            cancel_buttons.append((f"❌ لغو #{post_id}", f"cancel_confirm:{o['id']}"))

    for i in range(0, len(cancel_buttons), 2):
        rows.append(list(cancel_buttons[i:i+2]))

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"tracking_page:{page-1}"))
        nav.append((f"{page+1}/{total_pages}", "noop"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"tracking_page:{page+1}"))
        rows.append(nav)

    rows.append([("🔙 بازگشت به منوی اصلی", "tracking_back")])

    link_opts = LinkPreviewOptions(is_disabled=True)

    if is_first:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=inline(rows),
            link_preview_options=link_opts
        )
    else:
        q = update.callback_query
        try:
            await q.message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=inline(rows),
                link_preview_options=link_opts
            )
        except Exception:
            pass


# ==================== لغو سفارش ====================
def _calc_refund_by_panel(user_id, remaining_members):
    user = get_user(user_id)
    panel = user.get("panel", "عادی") if user else "عادی"
    panel_coin = {
        "عادی": 1.5,
        "حرفه ای": 2.0,
        "ویژه": 2.5,
    }.get(panel, 1.5)
    return int(remaining_members * panel_coin), panel_coin


async def cancel_order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])

    with db.conn() as c:
        order = c.execute("SELECT * FROM orders WHERE id=? AND admin_id=?", (order_id, user_id)).fetchone()
    if not order:
        await q.answer("❌ سفارش یافت نشد.", show_alert=True)
        return

    order = dict(order)
    if order["status"] != "running":
        await q.answer("❌ این سفارش فعال نیست.", show_alert=True)
        return

    # چک فعال بودن لغو (پاپ‌آپ)
    if get_setting("cancel_enabled", "on") != "on":
        await q.answer("⚠️ لغو سفارش غیرفعال است.", show_alert=True)
        return

    # چک زمان انتظار (به دقیقه) — پاپ‌آپ
    wait_minutes = int(get_setting("cancel_wait_minutes", "0") or 0)
    cancel_at = order.get("cancel_at") or 0

    if wait_minutes > 0 and now_ts() < cancel_at:
        remaining = cancel_at - now_ts()
        minutes = remaining // 60
        seconds = remaining % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        await q.answer(f"مدت انتظار لغو سفارش : {time_str}", show_alert=True)
        return

    # چک حداقل ممبر باقی‌مانده
    min_received = int(get_setting("cancel_min_members", "0") or 0)
    remaining_members = order["member_target"] - order["member_received"]

    # اگه باقی‌مانده کمتر از حداقل باشه → لغو غیرفعال
    # یعنی 1 <= remaining <= min_received-1 → نمی‌تونه لغو کنه
    if min_received > 0 and remaining_members <= min_received:
        await q.answer(
            f"⚠️ امکان لغو وجود ندارد.\n"
            f"حداقل مجاز برای لغو : {min_received}\n"
            f"مقدار ممبر باقی مانده شما : {remaining_members}",
            show_alert=True
        )
        return

    # محاسبه سکه بازگشتی
    refund, panel_coin = _calc_refund_by_panel(user_id, remaining_members)

    await q.answer()
    await q.message.reply_text(
        f"⁉️ آیا از لغو سفارش <b>#{order.get('post_id') or order_id}</b> مطمئن هستید؟\n\n"
        f"👥 ممبر باقی‌مانده: {remaining_members}\n"
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

        remaining_members = order["member_target"] - order["member_received"]
        refund, panel_coin = _calc_refund_by_panel(user_id, remaining_members)

        c.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
        c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (refund, user_id))
        c.execute("""
            INSERT INTO transactions (to_id, amount, type, description)
            VALUES (?, ?, 'order_cancel_refund', ?)
        """, (user_id, refund, f"بازگشت از سفارش #{order.get('post_id') or order_id}"))

    try:
        await context.bot.delete_message(f"@{Config.ADS_CHANNEL}", order["post_id"])
    except Exception:
        pass

    await q.answer(f"✅ سفارش لغو شد. {refund:,} سکه بازگشت.", show_alert=True)
    try:
        await q.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        user_id,
        f"✅ سفارش #{order.get('post_id') or order_id} با موفقیت لغو شد.\n"
        f"💰 {refund:,} سکه به حساب شما بازگشت.",
        reply_markup=main_menu(is_admin(user_id))
    )


# ==================== بازگشت به منو ====================
async def tracking_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(q.from_user.id))
    )


# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data

    if data.startswith("cancel_confirm:"):
        await cancel_order_confirm(update, context)
        return True
    if data.startswith("cancel_do:"):
        await cancel_order_do(update, context)
        return True
    if data == "tracking_back":
        await tracking_back(update, context)
        return True
    if data == "noop":
        await q.answer()
        return True
    if data.startswith("tracking_page:"):
        await q.answer()
        page = int(data.split(":")[1])
        user_id = q.from_user.id

        with db.conn() as c:
            orders = c.execute("""
                SELECT o.*,
                       (SELECT COUNT(*) FROM order_members om
                        WHERE om.order_id = o.id AND om.left_at IS NULL) as active_members,
                       (SELECT COUNT(*) FROM order_members om
                        WHERE om.order_id = o.id AND om.left_at IS NOT NULL) as left_members
                FROM orders o
                WHERE o.admin_id = ? AND o.status = 'running'
                ORDER BY o.post_id ASC
            """, (user_id,)).fetchall()

        orders = [dict(o) for o in orders]
        await _show_orders_page(update, context, orders, page, is_first=False)
        return True

    return False


# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return False
