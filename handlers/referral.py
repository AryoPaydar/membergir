from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from bot_manager import get_user, get_setting, get_user_state
from utils.keyboards import inline, back_button, main_menu
from utils.helpers import is_positive_int

async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    
    if get_setting("referral_enabled", "on") != "on":
        await update.message.reply_text("❌ زیرمجموعه‌گیری غیرفعال است.")
        return
    
    from database import db
    with db.conn() as c:
        count = c.execute("SELECT COUNT(*) c FROM users WHERE referrer_id = ?", (user.id,)).fetchone()["c"]
    
    banner_type = get_setting("referral_banner_type", "text")
    text = get_setting("referral_text", "🔗 لینک زیرمجموعه شما:")
    link = f"https://t.me/{bot_username}?start={user.id}"
    
    if banner_type == "photo":
        photo_id = get_setting("referral_photo_id", "")
        if photo_id:
            try:
                await context.bot.send_photo(
                    user.id, photo_id,
                    caption=f"{text}\n\n{link}\n\n👥 تعداد زیرمجموعه: {count}",
                    reply_markup=inline([[("🔙 بازگشت", "back")]])
                )
                return
            except Exception:
                pass
    
    await update.message.reply_text(
        f"{text}\n\n{link}\n\n👥 تعداد زیرمجموعه: {count}",
        reply_markup=inline([[("🔙 بازگشت", "back")]])
    )

# ==================== تنظیمات ادمین ====================
async def referral_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot_manager import is_admin, set_setting, get_setting
    if not is_admin(update.effective_user.id):
        return
    enabled = get_setting("referral_enabled", "on")
    report = get_setting("referral_report", "on")
    banner = get_setting("referral_banner_type", "text")
    threshold = get_setting("referral_join_threshold", str(Config.REFERRAL_JOIN_THRESHOLD))
    coin = get_setting("referral_join_coin", str(Config.REFERRAL_JOIN_COIN))
    
    await update.message.reply_text(
        "⚙️ تنظیمات زیرمجموعه‌گیری",
        reply_markup=inline([
            [(f"وضعیت: {'روشن ✅' if enabled=='on' else 'خاموش ❌'}", "ref_toggle")],
            [(f"گزارش: {'روشن ✅' if report=='on' else 'خاموش ❌'}", "ref_toggle_report")],
            [(f"نوع بنر: {banner}", "ref_toggle_banner")],
            [(f"آستانه عضویت: {threshold}", "ref_set_threshold")],
            [(f"سکه پورسانت: {coin}", "ref_set_coin")],
            [("📝 تنظیم متن", "ref_set_text")],
            [("🖼 تنظیم عکس", "ref_set_photo")],
        ])
    )

async def referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    from bot_manager import set_setting, get_setting, is_admin, set_user_state
    if not is_admin(q.from_user.id):
        return False
    
    if data == "ref_toggle":
        cur = get_setting("referral_enabled", "on")
        set_setting("referral_enabled", "off" if cur == "on" else "on")
        await q.answer("✅ تغییر کرد")
        await referral_admin(update, context)
        return True
    if data == "ref_toggle_report":
        cur = get_setting("referral_report", "on")
        set_setting("referral_report", "off" if cur == "on" else "on")
        await q.answer("✅")
        await referral_admin(update, context)
        return True
    if data == "ref_toggle_banner":
        cur = get_setting("referral_banner_type", "text")
        set_setting("referral_banner_type", "photo" if cur == "text" else "text")
        await q.answer("✅")
        await referral_admin(update, context)
        return True
    if data == "ref_set_threshold":
        set_user_state(q.from_user.id, "ref_set_threshold")
        await q.message.reply_text("👈 آستانه عضویت را وارد کنید:")
        return True
    if data == "ref_set_coin":
        set_user_state(q.from_user.id, "ref_set_coin")
        await q.message.reply_text("👈 تعداد سکه پورسانت را وارد کنید:")
        return True
    if data == "ref_set_text":
        set_user_state(q.from_user.id, "ref_set_text")
        await q.message.reply_text("📝 متن بنر را ارسال کنید:")
        return True
    if data == "ref_set_photo":
        set_user_state(q.from_user.id, "ref_set_photo")
        await q.message.reply_text("🖼 عکس بنر را ارسال کنید:")
        return True
    return False

async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    from bot_manager import is_admin, set_setting, set_user_state
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    state, _ = get_user_state(user_id)
    
    if state == "ref_set_threshold":
        if is_positive_int(update.message.text):
            set_setting("referral_join_threshold", update.message.text.strip())
            set_user_state(user_id, "none")
            await update.message.reply_text("✅")
            return True
    if state == "ref_set_coin":
        if is_positive_int(update.message.text):
            set_setting("referral_join_coin", update.message.text.strip())
            set_user_state(user_id, "none")
            await update.message.reply_text("✅")
            return True
    if state == "ref_set_text":
        set_setting("referral_text", update.message.text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅")
        return True
    if state == "ref_set_photo" and update.message.photo:
        set_setting("referral_photo_id", update.message.photo[-1].file_id)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅")
        return True
    return False

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return await referral_callback(update, context)
