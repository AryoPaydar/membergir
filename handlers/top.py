from telegram import Update
from telegram.ext import ContextTypes
from database import db
from bot_manager import is_admin
from utils.keyboards import inline, main_menu

async def top_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 <b>برترین کاربران</b>\n\nدسته‌بندی مورد نظر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=inline([
            [("👥 برترین زیرمجموعه‌گیرها", "top_ref")],
            [("🔗 برترین اعضای کانال", "top_join")],
            [("📌 برترین سفارش‌دهنده‌ها", "top_orders")],
        ])
    )

async def top_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT u.user_id, u.first_name, COUNT(r.user_id) as cnt
            FROM users u
            LEFT JOIN users r ON r.referrer_id = u.user_id
            GROUP BY u.user_id
            HAVING cnt > 0
            ORDER BY cnt DESC
            LIMIT 10
        """).fetchall()
    
    text = "🏆 <b>برترین‌های زیرمجموعه‌گیری</b>\n\n"
    if not rows:
        text += "هنوز کسی زیرمجموعه جذب نکرده."
    else:
        for i, r in enumerate(rows, 1):
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            text += f"{emoji} {r['first_name'] or 'کاربر'} - <code>{r['user_id']}</code>\n👥 تعداد: {r['cnt']}\n\n"
    
    await q.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "top_back")]])
    )

async def top_joiners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT user_id, first_name, ads_joined
            FROM users
            WHERE ads_joined > 0
            ORDER BY ads_joined DESC
            LIMIT 10
        """).fetchall()
    
    text = "🏆 <b>برترین‌های عضویت در کانال</b>\n\n"
    if not rows:
        text += "هنوز کسی عضویتی انجام نداده."
    else:
        for i, r in enumerate(rows, 1):
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            text += f"{emoji} {r['first_name'] or 'کاربر'} - <code>{r['user_id']}</code>\n🔗 تعداد: {r['ads_joined']}\n\n"
    
    await q.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "top_back")]])
    )

async def top_orderers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT user_id, first_name, orders_count
            FROM users
            WHERE orders_count > 0
            ORDER BY orders_count DESC
            LIMIT 10
        """).fetchall()
    
    text = "🏆 <b>برترین‌های ثبت سفارش</b>\n\n"
    if not rows:
        text += "هنوز کسی سفارشی ثبت نکرده."
    else:
        for i, r in enumerate(rows, 1):
            emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            text += f"{emoji} {r['first_name'] or 'کاربر'} - <code>{r['user_id']}</code>\n📌 تعداد: {r['orders_count']}\n\n"
    
    await q.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "top_back")]])
    )

async def top_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        "🏆 <b>برترین کاربران</b>\n\nدسته‌بندی مورد نظر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=inline([
            [("👥 برترین زیرمجموعه‌گیرها", "top_ref")],
            [("🔗 برترین اعضای کانال", "top_join")],
            [("📌 برترین سفارش‌دهنده‌ها", "top_orders")],
        ])
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    handlers = {
        "top_ref": top_referrals,
        "top_join": top_joiners,
        "top_orders": top_orderers,
        "top_back": top_back,
    }
    if data in handlers:
        await handlers[data](update, context)
        return True
    return False