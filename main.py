import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, filters
)
from config import Config
from database import db
from bot_manager import (
    get_user, create_user, is_admin, is_banned, is_bot_on, get_setting, set_user_state
)
from handlers import (
    user, admin, ads, transfer, referral, gift, shop,
    panel, orders_history, top, admin_shop, admin_texts, history,
    admin_coins, admin_user_info, admin_complete, admin_channels,
    admin_cancel, admin_transfer, admin_referral, admin_panels, admin_orders,
    admin_ads_channels,
)
from utils.keyboards import main_menu, admin_panel

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
    "🏦 بانک انتقال": history.history_menu,
    "⚖️ قوانین": user.rules,
    "💡راهنما": user.help_menu,
    "📨 ارتباط با مدیریت": user.contact_admin,
    "💞حمایت مالی": user.support,
}

ADMIN_BUTTONS = {
    "📈 آمار ربات": admin.stats,
    "📨 ارسال پیام": admin.broadcast_start,
    "🏦 مبادلات سکه": admin_coins.coins_menu,
    "📌 تنظیم سفارش": admin_orders.orders_menu,
    "♻️ پنل‌ها": admin_panels.panels_menu,
    "👤 ادمین‌ها": admin.admins_menu,
    "👥 مدیریت کاربران": admin_user_info.users_menu,
    "📇 تنظیم متن": admin_texts.texts_menu,
    "📇 تنظیم متن‌ها": admin_texts.texts_menu,
    "🆔 تنظیم کانال": admin_channels.channels_menu,
    "⚠️ اخطاردهی": admin.warn_user,
    "⚙️ زیرمجموعه‌گیری": admin_referral.referral_menu,
    "🎗 تکمیل سفارش": admin_complete.complete_menu,
    "🔮 جستجوگر": admin_user_info.search_menu,
    "✂️ تنظیمات لغو": admin_cancel.cancel_menu,
    "💳 تنظیمات انتقال": admin_transfer.transfer_menu,
    "🔕 خاموش/روشن": admin.power_menu,
    "🔙 بازگشت به منو": admin.back_to_main,
}


# ==================== ردیاب کانال/گروه ====================
async def track_chat(update: Update, context):
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
        logger.info(f"✅ ربات به {chat.type} {chat.title} (ID: {chat.id}) اضافه شد")
    elif new_status in ("left", "kicked"):
        with db.conn() as c:
            c.execute("DELETE FROM bot_chats WHERE chat_id = ?", (chat.id,))
        logger.info(f"❌ ربات از {chat.type} {chat.title} (ID: {chat.id}) حذف شد")


async def on_message(update: Update, context):
    user_tg = update.effective_user
    msg = update.message
    text = (msg.text or "").strip()

    logger.info(f"📨 on_message: '{text}' from user {user_tg.id} ({user_tg.first_name})")

    if is_banned(user_tg.id):
        logger.info(f"⛔️ User {user_tg.id} is banned")
        return

    if not is_bot_on() and not is_admin(user_tg.id):
        await msg.reply_text(get_setting("power_text", "ربات خاموش است."))
        return

    if not get_user(user_tg.id):
        create_user(user_tg.id, user_tg.first_name or "", user_tg.username or "")
        logger.info(f"✅ Created user {user_tg.id}")

    # ۱. State کاربر
    for module in (user, history, gift, ads, transfer, referral, shop, panel, orders_history):
        if hasattr(module, "handle_state"):
            try:
                if await module.handle_state(update, context):
                    logger.info(f"✅ {module.__name__}.handle_state handled")
                    return
            except Exception as e:
                logger.exception(f"State error in {module.__name__}: {e}")

    # ۲. State ادمین
    if is_admin(user_tg.id):
        logger.info(f"👑 User {user_tg.id} is admin")

        # دکمه بازگشت به پنل مدیریت (از زیرمنوهای ادمین)
        if text == "🔙 بازگشت به پنل مدیریت":
            set_user_state(user_tg.id, "none")
            await msg.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
            logger.info("✅ بازگشت به پنل مدیریت")
            return

        admin_modules = (
            admin, admin_shop, admin_texts, admin_coins, admin_user_info,
            admin_complete, admin_channels, admin_ads_channels,
            admin_cancel, admin_transfer, admin_referral, admin_panels, admin_orders,
        )
        for module in admin_modules:
            if hasattr(module, "handle_state"):
                try:
                    if await module.handle_state(update, context):
                        logger.info(f"✅ admin {module.__name__}.handle_state handled")
                        return
                except Exception as e:
                    logger.exception(f"Admin state error in {module.__name__}: {e}")

        # 🔮 state جستجوگر
        if await admin_user_info.handle_srch_state(update, context):
            logger.info("✅ admin_user_info.handle_srch_state handled")
            return

        if await admin.handle_text(update, context):
            logger.info("✅ admin.handle_text handled")
            return

        if text == "🎉 کد هدیه":
            await gift.gift_admin_menu(update, context)
            logger.info("✅ gift.gift_admin_menu handled")
            return

        if text in ADMIN_BUTTONS and ADMIN_BUTTONS[text]:
            try:
                await ADMIN_BUTTONS[text](update, context)
                logger.info(f"✅ ADMIN_BUTTON: {text}")
                return
            except Exception as e:
                logger.exception(f"ADMIN_BUTTON error for '{text}': {e}")

        logger.info(f"❌ No admin handler for: '{text}'")

    # ۳. دکمه‌های بانک
    if text == "💎 انتقال الماس":
        await history.transfer_start(update, context)
        return
    if text == "📥 تاریخچه دریافت":
        await history.history_received(update, context)
        return
    if text == "📤 تاریخچه انتقال":
        await history.history_sent(update, context)
        return
    if text == "🔙 بازگشت به منوی اصلی":
        await user.back_to_menu(update, context)
        return
    if text == "🔙 بازگشت به صفحه اصلی":
        await user.back_to_menu(update, context)
        return

    # ۴. دکمه‌های کاربر
    if text in USER_BUTTONS:
        try:
            await USER_BUTTONS[text](update, context)
            logger.info(f"✅ USER_BUTTON: {text}")
            return
        except Exception as e:
            logger.exception(f"USER_BUTTON error for '{text}': {e}")

    if text == "🔙 بازگشت":
        await user.back_to_menu(update, context)
        logger.info("✅ back_to_menu handled")
        return

    logger.info(f"❓ Unknown command: '{text}'")
    await msg.reply_text(
        "❓ دستور نامعتبر.",
        reply_markup=main_menu(is_admin(user_tg.id))
    )


async def on_callback(update: Update, context):
    q = update.callback_query
    logger.info(f"🔔 on_callback: '{q.data}' from user {q.from_user.id}")

    if is_banned(q.from_user.id):
        await q.answer()
        return

    if not is_bot_on() and not is_admin(q.from_user.id):
        await q.answer("ربات خاموش است.", show_alert=True)
        return

    modules = [
        admin_user_info,
        history,
        orders_history,
        gift, ads, user, admin,
        admin_coins, admin_complete,
        admin_ads_channels,
        admin_channels,
        admin_cancel, admin_transfer, admin_referral, admin_panels, admin_orders,
        transfer, referral, shop, panel, top,
        admin_shop, admin_texts,
    ]
    for module in modules:
        if hasattr(module, "handle_callback"):
            try:
                if await module.handle_callback(update, context):
                    logger.info(f"✅ {module.__name__}.handle_callback handled: '{q.data}'")
                    return
            except Exception as e:
                logger.exception(f"Callback error in {module.__name__}: {e}")

    logger.info(f"❓ Callback not handled: '{q.data}'")
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
    app.add_handler(ChatMemberHandler(track_chat, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_error_handler(on_error)

    logger.info("Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
