from telegram import Update
from telegram.ext import ContextTypes
from database import db
from bot_manager import get_user, is_admin
from utils.keyboards import inline, main_menu
from utils.helpers import format_number

# ==================== منوی تاریخچه ====================
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 <b>تاریخچه تراکنش‌ها</b>\n\nنوع تراکنش را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=inline([
            [("📥 دریافتی‌ها", "hist_received")],
            [("📤 ارسالی‌ها", "hist_sent")],
            [("💰 همه", "hist_all")],
        ])
    )

async def show_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT * FROM transactions
            WHERE to_id = ?
            ORDER BY id DESC LIMIT 20
        """, (user_id,)).fetchall()
    
    if not rows:
        await q.message.edit_text(
            "📭 تراکنش دریافتی‌ای ثبت نشده.",
            reply_markup=inline([[("🔙 بازگشت", "hist_back")]])
        )
        return
    
    text = "📥 <b>دریافتی‌های اخیر:</b>\n\n"
    for r in rows:
        from_user = f"از {r['from_id']}" if r['from_id'] else "سیستم"
        text += (
            f"💰 +{r['amount']:,} سکه\n"
            f"🔖 {r['description'] or r['type']}\n"
            f"👤 {from_user}\n"
            f"📆 {r['created_at']}\n"
            f"——————\n"
        )
    
    await q.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "hist_back")]])
    )

async def show_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT * FROM transactions
            WHERE from_id = ?
            ORDER BY id DESC LIMIT 20
        """, (user_id,)).fetchall()
    
    if not rows:
        await q.message.edit_text(
            "📭 تراکنش ارسالی‌ای ثبت نشده.",
            reply_markup=inline([[("🔙 بازگشت", "hist_back")]])
        )
        return
    
    text = "📤 <b>ارسالی‌های اخیر:</b>\n\n"
    for r in rows:
        to_user = f"به {r['to_id']}" if r['to_id'] else "سیستم"
        text += (
            f"💸 -{r['amount']:,} سکه\n"
            f"🔖 {r['description'] or r['type']}\n"
            f"👤 {to_user}\n"
            f"📆 {r['created_at']}\n"
            f"——————\n"
        )
    
    await q.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "hist_back")]])
    )

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT * FROM transactions
            WHERE from_id = ? OR to_id = ?
            ORDER BY id DESC LIMIT 30
        """, (user_id, user_id)).fetchall()
    
    if not rows:
        await q.message.edit_text(
            "📭 تراکنشی ثبت نشده.",
            reply_markup=inline([[("🔙 بازگشت", "hist_back")]])
        )
        return
    
    text = "📜 <b>همه تراکنش‌ها:</b>\n\n"
    for r in rows:
        sign = "+" if r['to_id'] == user_id else "-"
        text += (
            f"{sign}{r['amount']:,} | {r['description'] or r['type']}\n"
            f"📆 {r['created_at']}\n"
            f"——————\n"
        )
    
    await q.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "hist_back")]])
    )

async def hist_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        "📜 <b>تاریخچه تراکنش‌ها</b>\n\nنوع تراکنش را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=inline([
            [("📥 دریافتی‌ها", "hist_received")],
            [("📤 ارسالی‌ها", "hist_sent")],
            [("💰 همه", "hist_all")],
        ])
    )

# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    handlers = {
        "hist_received": show_received,
        "hist_sent": show_sent,
        "hist_all": show_all,
        "hist_back": hist_back,
    }
    if data in handlers:
        await handlers[data](update, context)
        return True
    return False