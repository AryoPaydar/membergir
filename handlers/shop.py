from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import get_user, set_user_state, get_user_state, is_admin
from utils.keyboards import inline, main_menu
from utils.helpers import is_positive_int

async def shop_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user.get("phone"):
        set_user_state(user["user_id"], "shop_phone")
        from telegram import KeyboardButton, ReplyKeyboardMarkup
        await update.message.reply_text(
            "📱 لطفاً شماره موبایل خود را تأیید کنید:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("📱 ارسال شماره", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
        return
    await update.message.reply_text(
        "🛍 فروشگاه",
        reply_markup=inline([
            [("💰 خرید سکه", "shop_coin")],
            [("♻️ خرید پنل", "shop_panel")],
        ])
    )

async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    state, _ = get_user_state(user_id)
    if state != "shop_phone":
        return False
    msg = update.message
    if not msg.contact:
        await msg.reply_text("❌ لطفاً از دکمه ارسال شماره استفاده کنید.")
        return True
    if msg.contact.user_id != user_id:
        await msg.reply_text("❌ شماره باید متعلق به خودتان باشد.")
        return True
    phone = str(msg.contact.phone_number).replace("+", "")
    if not phone.startswith("98"):
        await msg.reply_text("❌ فقط شماره ایران مجاز است.")
        return True
    from bot_manager import update_user
    update_user(user_id, phone=phone)
    set_user_state(user_id, "none")
    await msg.reply_text("✅ شماره تأیید شد.", reply_markup=main_menu(is_admin(user_id)))
    return True

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if data == "shop_coin":
        await q.answer()
        with db.conn() as c:
            items = c.execute("SELECT * FROM shop_items WHERE item_type='coin' ORDER BY position").fetchall()
        if not items:
            await q.message.reply_text("❌ آیتمی تنظیم نشده.")
            return True
        rows = []
        for it in items:
            rows.append([(f"{it['name']} | {it['coin_amount']} سکه | {it['price']:,} ریال", f"buy_coin:{it['id']}")])
        rows.append([("🔙 بازگشت", "back")])
        await q.message.reply_text("💰 آیتم مورد نظر:", reply_markup=inline(rows))
        return True
    if data == "shop_panel":
        await q.answer()
        with db.conn() as c:
            items = c.execute("SELECT * FROM shop_items WHERE item_type='panel' ORDER BY position").fetchall()
        if not items:
            await q.message.reply_text("❌ آیتمی تنظیم نشده.")
            return True
        rows = []
        for it in items:
            rows.append([(f"{it['name']} | {it['panel_name']} {it['panel_days']} روز | {it['price']:,} ریال", f"buy_panel:{it['id']}")])
        rows.append([("🔙 بازگشت", "back")])
        await q.message.reply_text("♻️ آیتم مورد نظر:", reply_markup=inline(rows))
        return True
    if data.startswith("buy_coin:") or data.startswith("buy_panel:"):
        await q.answer("⚠️ درگاه پرداخت باید تنظیم شود.", show_alert=True)
        return True
    return False