from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from bot_manager import (
    get_user, transfer_coins, set_user_state, get_user_state, is_admin
)
from utils.keyboards import main_menu, inline
from utils.helpers import is_positive_int

async def transfer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Config.TRANSFER_ENABLED:
        await update.message.reply_text("❌ انتقال سکه غیرفعال است.")
        return
    user_id = update.effective_user.id
    set_user_state(user_id, "transfer_target")
    await update.message.reply_text(
        "💰 آیدی عددی کاربر مقصد را ارسال کنید:\n\n"
        "🆔 آیدی خود را از بخش «حساب کاربری» می‌توانید ببینید.",
        reply_markup=inline([[("🔙 بازگشت", "back")]])
    )

async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    state, data = get_user_state(user_id)
    
    if state == "transfer_target":
        text = (update.message.text or "").strip()
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط آیدی عددی مجاز است.")
            return True
        target = int(text)
        if target == user_id:
            await update.message.reply_text("❌ نمی‌توانید به خودتان انتقال دهید.")
            return True
        target_user = get_user(target)
        if not target_user:
            await update.message.reply_text("❌ کاربر یافت نشد.")
            return True
        set_user_state(user_id, "transfer_amount", {"target": target})
        await update.message.reply_text(
            f"💰 مقدار سکه مورد نظر را ارسال کنید:\n\n"
            f"👈 حداقل: {Config.TRANSFER_MIN}\n"
            f"👈 حداکثر: {Config.TRANSFER_MAX}\n"
            f"💳 موجودی شما: {get_user(user_id)['coins']:,}"
        )
        return True
    
    if state == "transfer_amount":
        text = (update.message.text or "").strip()
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        amount = int(text)
        if amount < Config.TRANSFER_MIN or amount > Config.TRANSFER_MAX:
            await update.message.reply_text(
                f"❌ مقدار باید بین {Config.TRANSFER_MIN} و {Config.TRANSFER_MAX} باشد."
            )
            return True
        target = data.get("target")
        if not target:
            set_user_state(user_id, "none")
            await update.message.reply_text("❌ خطا. دوباره تلاش کنید.")
            return True
        
        success = transfer_coins(user_id, target, amount)
        if not success:
            await update.message.reply_text("❌ موجودی کافی نیست.")
            set_user_state(user_id, "none")
            return True
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"✅ انتقال موفق!\n💰 {amount:,} سکه به کاربر {target} منتقل شد.",
            reply_markup=main_menu(is_admin(user_id))
        )
        try:
            await context.bot.send_message(
                target,
                f"✅ {amount:,} سکه از کاربر {user_id} دریافت کردید."
            )
        except Exception:
            pass
        
        if is_admin(Config.ADMIN_ID) and get_user(user_id):
            from bot_manager import get_setting
            if get_setting("transfer_report", "on") == "on":
                try:
                    await context.bot.send_message(
                        Config.ADMIN_ID,
                        f"💸 انتقال سکه\nاز: {user_id}\nبه: {target}\nمقدار: {amount}"
                    )
                except Exception:
                    pass
        return True
    
    return False