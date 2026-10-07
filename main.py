import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ChatMemberHandler, ChatJoinRequestHandler, filters
)
from config import Config
from database import db
from bot_manager import (
    get_user, create_user, is_admin, is_banned, is_bot_on, get_setting,
    set_user_state, get_leave_penalty, penalize_leaver,
    find_pending_leaves, refund_to_order_owner
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


# ==================== چک انقضای هدیه اعتباری ====================
async def _handle_credit_gift_expiry(context, user_id: int):
    """اگه هدیه اعتباری منقضی شده، از coins کم کن و پیام بفرست"""
    from utils.helpers import now_ts
    now = now_ts()

    with db.conn() as c:
        row = c.execute("""
            SELECT credit_gift, credit_gift_expire, coins
            FROM users
            WHERE user_id = ? AND credit_gift > 0 AND credit_gift_expire > 0 AND credit_gift_expire <= ?
        """, (user_id, now)).fetchone()

    if not row:
        return

    lost = row["credit_gift"]
    if lost <= 0:
        return

    with db.conn() as c:
        c.execute("""
            UPDATE users SET
                coins = MAX(0, coins - ?),
                credit_gift = 0,
                credit_gift_expire = 0
            WHERE user_id = ?
        """, (lost, user_id))

    logger.info(f"⏰ Credit gift expired for {user_id}, lost={lost}")

    try:
        await context.bot.send_message(
            user_id,
            f"⏰ هدیه اعتباری شما منقضی شد!\n\n"
            f"💸 مقدار هدیه از دست رفته : {lost:,}"
        )
    except Exception as e:
        logger.error(f"credit gift expiry msg error: {e}")


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


async def on_chat_member(update: Update, context):
    """
    وقتی عضوی از کانال/گروه لفت می‌ده یا kick میشه:
    - چک کن توی order_members رکورد فعال داشته
    - اگه کمتر از 3 روز از claim گذشته باشه → جریمه کن
    - به سفارش‌دهنده 2 سکه برگردون
    """
    cm = update.chat_member
    if not cm:
        return

    new_status = cm.new_chat_member.status
    old_status = cm.old_chat_member.status
    chat = cm.chat
    member = cm.new_chat_member.user

    # فقط وقتی از حالت member/administrator/creator خارج شده
    if new_status not in ("left", "kicked"):
        return
    if old_status not in ("member", "administrator", "creator"):
        return

    user_id = member.id

    # خود ربات رو نادیده بگیر
    try:
        me = await context.bot.get_me()
        if user_id == me.id:
            return
    except Exception:
        pass

    logger.info(f"👋 User {user_id} left/kicked from {chat.id} ({chat.title})")

    pending = find_pending_leaves(user_id)
    if not pending:
        return

    for rec in pending:
        order_channel = rec.get("channel", "").lstrip("@")
        chat_username = (chat.username or "").lstrip("@")
        order_channel_id = rec.get("channel_id")

        matched = False
        # 1) با chat_id سفارش
        if order_channel_id and int(order_channel_id) == int(chat.id):
            matched = True
        # 2) با یوزرنیم
        elif chat_username and order_channel and chat_username.lower() == order_channel.lower():
            matched = True

        if not matched:
            continue

        user = get_user(user_id)
        if not user:
            continue

        penalty = get_leave_penalty(user)

        ok = penalize_leaver(user_id, rec["id"], penalty)
        if not ok:
            continue

        logger.info(
            f"💸 Penalized user {user_id} amount={penalty} "
            f"for order #{rec['order_id']}"
        )

        # پیام به لفت‌دهنده
        try:
            await context.bot.send_message(
                user_id,
                f"⚠️ شما کمتر از 3 روز از کانال @{order_channel} لفت دادید.\n"
                f"💸 {penalty:g} سکه از حساب شما کسر شد."
            )
        except Exception:
            pass

        # برگرداندن 2 سکه به سفارش‌دهنده + پیام
        try:
            refund_to_order_owner(rec["admin_id"], rec["order_id"], 2)
            await context.bot.send_message(
                rec["admin_id"],
                f"🛡 یک کاربر کمتر از 3 روز از سفارش شما لفت داده است "
                f"به همین خاطر 2 سکه به شما بازگشت داده شد."
            )
        except Exception as e:
            logger.error(f"refund to owner error: {e}")


async def on_message(update: Update, context):
    user_tg = update.effective_user
    msg = update.message
    text = (msg.text or "").strip()

    if update.effective_chat.type != "private":
        return

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

    # 👈 چک انقضای هدیه اعتباری
    await _handle_credit_gift_expiry(context, user_tg.id)

    # چک جوین اجباری
    if not is_admin(user_tg.id) and not text.startswith("/start"):
        from handlers.user import check_force_join
        if not await check_force_join(context, user_tg.id):
            logger.info(f"🔐 User {user_tg.id} not joined force channels")
            return

    for module in (user, history, gift, ads, transfer, referral, shop, panel, orders_history):
        if hasattr(module, "handle_state"):
            try:
                if await module.handle_state(update, context):
                    logger.info(f"✅ {module.__name__}.handle_state handled")
                    return
            except Exception as e:
                logger.exception(f"State error in {module.__name__}: {e}")

    if is_admin(user_tg.id):
        logger.info(f"👑 User {user_tg.id} is admin")

        if text == "🔙 بازگشت به پنل مدیریت":
            set_user_state(user_tg.id, "none")
            await msg.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
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

    if text in USER_BUTTONS:
        try:
            await USER_BUTTONS[text](update, context)
            logger.info(f"✅ USER_BUTTON: {text}")
            return
        except Exception as e:
            logger.exception(f"USER_BUTTON error for '{text}': {e}")

    if text == "🔙 بازگشت":
        await user.back_to_menu(update, context)
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

    # 👈 چک انقضای هدیه اعتباری
    await _handle_credit_gift_expiry(context, q.from_user.id)

    if not is_admin(q.from_user.id) and q.data not in ("check_join",):
        from handlers.user import check_force_join
        if not await check_force_join(context, q.from_user.id):
            await q.answer("🔐 ابتدا عضو کانال شوید!", show_alert=True)
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


# ==================== حلقه پس‌زمینه چک انقضای هدیه اعتباری ====================
_bot_instance = None


async def credit_gift_loop():
    """هر 60 ثانیه هدیه‌های اعتباری منقضی‌شده رو چک کن"""
    from utils.helpers import now_ts
    logger.info("🔁 credit_gift_loop started")
    while True:
        try:
            now = now_ts()
            with db.conn() as c:
                expired = c.execute("""
                    SELECT user_id, credit_gift FROM users
                    WHERE credit_gift > 0 AND credit_gift_expire > 0 AND credit_gift_expire <= ?
                """, (now,)).fetchall()
                expired_users = [dict(r) for r in expired]

            for row in expired_users:
                uid = row["user_id"]
                lost = row["credit_gift"]

                with db.conn() as c:
                    c.execute("""
                        UPDATE users SET
                            coins = MAX(0, coins - ?),
                            credit_gift = 0,
                            credit_gift_expire = 0
                        WHERE user_id = ?
                    """, (lost, uid))

                logger.info(f"⏰ Credit gift expired for {uid}, lost={lost}")

                if _bot_instance:
                    try:
                        await _bot_instance.send_message(
                            uid,
                            f"⏰ هدیه اعتباری شما منقضی شد!\n\n"
                            f"💸 مقدار هدیه از دست رفته : {lost:,}"
                        )
                    except Exception as e:
                        logger.error(f"credit gift msg error to {uid}: {e}")

        except Exception as e:
            logger.error(f"credit_gift_loop error: {e}")

        await asyncio.sleep(60)


async def on_join_request(update: Update, context):
    req = update.chat_join_request
    if not req:
        return

    user_id = req.from_user.id
    chat_id = req.chat.id

    with db.conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO pending_joins (user_id, chat_id)
            VALUES (?, ?)
        """, (user_id, chat_id))
        c.execute("""
            UPDATE ads_channels_tg SET chat_id = ?
            WHERE chat_id IS NULL
        """, (chat_id,))

    try:
        await context.bot.approve_chat_join_request(chat_id, user_id)
    except Exception:
        pass

    logger.info(f"✅ Join request از {user_id} برای chat_id={chat_id} ثبت شد")


async def on_error(update: object, context):
    logger.error(f"Exception: {context.error}", exc_info=context.error)


def main():
    global _bot_instance

    logger.info("Starting bot...")
    app = Application.builder().token(Config.BOT_TOKEN).build()

    app.add_handler(CommandHandler(
        "start", user.start,
        filters=filters.ChatType.PRIVATE
    ))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.ALL & ~filters.COMMAND,
        on_message
    ))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(ChatMemberHandler(track_chat, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_error_handler(on_error)

    _bot_instance = app.bot

    async def post_init(application):
        asyncio.create_task(credit_gift_loop())
        logger.info("✅ credit_gift_loop task created")

    app.post_init = post_init

    logger.info("Bot is running.")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES + ["chat_join_request"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
