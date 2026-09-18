import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, filters
)
from config import Config
from database import db
from bot_manager import (
    get_user, create_user, is_admin, is_banned, is_bot_on, get_setting
)
from handlers import (
    user, admin, ads, transfer, referral, gift, shop,
    panel, orders_history, top, admin_shop, admin_texts, history,
)
from utils.keyboards import main_menu

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== دکمه‌های منو ====================
USER_BUTTONS = {
    "💰 دریافت سکه": user.daily_coin,
    "👤 حساب کاربری": user.account,
    "🚀 ثبت سفارش": ads.order_menu,
    "👥 زیرمجموعه‌گیری": referral.referral_menu,
    "🎁 کد هدیه": gift.gift_menu,
    "🛍 فروشگاه": shop.shop_menu,
    "📋 پیگیری سفارش": orders_history.tracking_menu,
    "🚀 ارتقا پنل": panel.panel_menu,
    "🏆 برترین‌ها": top.top_menu,
    "📜 تاریخچه تراکنش": history.history_menu,
}

ADMIN_BUTTONS = {
    "🛍 مدیریت فروشگاه": admin_shop.shop_admin_menu,
    "📇 تنظیم متن‌ها": admin_texts.texts_menu,
}


# ==================== ردیاب کانال/گروه ====================
async def track_chat(update: Update, context):
    """وقتی ربات به کانال/گروهی اضافه یا حذف میشه"""
    my_chat_member = update.my_chat_member
    if not my_chat_member:
        return
    
    chat = my_chat_member.chat
    new_status = my_chat_member.new_chat_member.status
    
    if new_status in ("administrator", "member", "creator"):
        with db.conn() as c:
            c.execute("""
                INSERT INTO bot_chats (chat_id, chat_type, title, username)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_type = excluded.chat_type,
                    title = excluded.title,
                    username = excluded.username
            """, (chat.id, chat.type, chat.title or "", chat.username or ""))
        print(f"✅ ربات به {chat.type} {chat.title} (ID: {chat.id}) اضافه شد")
    
    elif new_status in ("left", "kicked"):
        with db.conn() as c:
            c.execute("DELETE FROM bot_chats WHERE chat_id = ?", (chat.id,))
        print(f"❌ ربات از {chat.type} {chat.title} (ID: {chat.id}) حذف شد")


async def on_message(update: Update, context):
    user_tg = update.effective_user
    msg = update.message
    text = (msg.text or "").strip()
    
    if is_banned(user_tg.id):
        return
    
    if not is_bot_on() and not is_admin(user_tg.id):
        await msg.reply_text(get_setting("power_text", "ربات خاموش است."))
        return
    
    if not get_user(user_tg.id):
        create_user(user_tg.id, user_tg.first_name or "", user_tg.username or "")
    
    # ۱. State کاربر — gift اول
    for module in (gift, ads, transfer, referral, shop, panel, orders_history):
        if hasattr(module, "handle_state"):
            if await module.handle_state(update, context):
                return
    
    # ۲. State ادمین — gift دوم
    if is_admin(user_tg.id):
        for module in (gift, admin, admin_shop, admin_texts):
            if hasattr(module, "handle_state"):
                if await module.handle_state(update, context):
                    return
        if await admin.handle_text(update, context):
            return
        if text in ADMIN_BUTTONS:
            await ADMIN_BUTTONS[text](update, context)
            return
    
    # ۳. دکمه‌های کاربر
    if text in USER_BUTTONS:
        await USER_BUTTONS[text](update, context)
        return
    
    if text == "🔙 بازگشت":
        await user.back_to_menu(update, context)
        return
    
    await msg.reply_text(
        "❓ دستور نامعتبر.",
        reply_markup=main_menu(is_admin(user_tg.id))
    )


async def on_callback(update: Update, context):
    q = update.callback_query
    
    if is_banned(q.from_user.id):
        await q.answer()
        return
    
    if not is_bot_on() and not is_admin(q.from_user.id):
        await q.answer("ربات خاموش است.", show_alert=True)
        return
    
    # 👇 ترتیب مهم: gift اول
    modules = [
        gift,
        ads,
        user,
        admin,
        transfer,
        referral,
        shop,
        panel,
        orders_history,
        top,
        admin_shop,
        admin_texts,
        history,
    ]
    for module in modules:
        if hasattr(module, "handle_callback"):
            try:
                if await module.handle_callback(update, context):
                    return
            except Exception as e:
                logger.exception(f"Callback error in {module.__name__}: {e}")
    
    try:
        await q.answer()
    except Exception:
        pass


async def on_error(update: object, context):
    logger.error(f"Exception: {context.error}", exc_info=context.error)


def main():
    logger.info("Starting bot...")
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", user.start))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(
        ChatMemberHandler(track_chat, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_error_handler(on_error)
    
    logger.info("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
