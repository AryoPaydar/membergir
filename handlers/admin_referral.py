from telegram import Update
from telegram.ext import ContextTypes
from bot_manager import is_admin, set_user_state, get_user_state, set_setting, get_setting
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int


async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    
    power = get_setting("referral_enabled", "on")
    report = get_setting("referral_report", "on")
    banner = get_setting("referral_banner_type", "text")
    threshold = get_setting("referral_join_threshold", "10")
    coin = get_setting("referral_join_coin", "5")
    
    await update.message.reply_text(
        "گزینه مورد نظر را انتخاب نمایید",
        reply_markup=inline([
            [("وضعیت: " + ("✅فعال" if power == "on" else "❌غیر فعال"), "arf_power"), ("گزارش: " + ("✅فعال" if report == "on" else "❌غیر فعال"), "arf_report")],
            [("📃نوع بنر: " + banner, "arf_banner")],
            [(f"👤آستانه: {threshold}", "arf_threshold"), (f"💰سکه پورسانت: {coin}", "arf_coin")],
            [("📝تنظیم متن بنر", "arf_set_text"), ("🖼تنظیم عکس بنر", "arf_set_photo")],
            [("🔙 بازگشت به پنل مدیریت", "arf_back")],
        ])
    )


async def arf_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if not state or state == "none":
        return False
    
    if text == "🔙 بازگشت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True
    
    if state == "arf_threshold":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting("referral_join_threshold", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    if state == "arf_coin":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting("referral_join_coin", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    if state == "arf_set_text":
        set_setting("referral_text", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    if state == "arf_set_photo":
        if update.message.photo:
            set_setting("referral_photo_id", update.message.photo[-1].file_id)
            set_user_state(user_id, "none")
            await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        else:
            await update.message.reply_text("❌ لطفا عکس ارسال کنید.")
        return True
    
    return False


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data == "arf_power":
        await q.answer()
        cur = get_setting("referral_enabled", "on")
        set_setting("referral_enabled", "off" if cur == "on" else "on")
        await referral_menu(update, context)
        return True
    if data == "arf_report":
        await q.answer()
        cur = get_setting("referral_report", "on")
        set_setting("referral_report", "off" if cur == "on" else "on")
        await referral_menu(update, context)
        return True
    if data == "arf_banner":
        await q.answer()
        cur = get_setting("referral_banner_type", "text")
        set_setting("referral_banner_type", "photo" if cur == "text" else "text")
        await referral_menu(update, context)
        return True
    if data == "arf_threshold":
        await q.answer()
        set_user_state(q.from_user.id, "arf_threshold")
        await q.message.reply_text("آستانه عضویت زیرمجموعه را وارد کنید:", reply_markup=back_button())
        return True
    if data == "arf_coin":
        await q.answer()
        set_user_state(q.from_user.id, "arf_coin")
        await q.message.reply_text("تعداد سکه پورسانت را وارد کنید:", reply_markup=back_button())
        return True
    if data == "arf_set_text":
        await q.answer()
        set_user_state(q.from_user.id, "arf_set_text")
        await q.message.reply_text("متن بنر زیرمجموعه‌گیری را ارسال کنید:", reply_markup=back_button())
        return True
    if data == "arf_set_photo":
        await q.answer()
        set_user_state(q.from_user.id, "arf_set_photo")
        await q.message.reply_text("عکس بنر را ارسال کنید:", reply_markup=back_button())
        return True
    if data == "arf_back":
        await arf_back(update, context)
        return True
    return False
