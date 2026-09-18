from telegram import Update
from telegram.ext import ContextTypes
from bot_manager import is_admin, set_user_state, get_user_state, set_setting, get_setting
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int


async def cancel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    
    cond = get_setting("cancel_enabled", "on")
    min_members = get_setting("cancel_min_members", "100")
    wait_seconds = get_setting("cancel_wait_seconds", "60")
    refund_ratio = get_setting("cancel_refund_ratio", "0.5")
    
    await update.message.reply_text(
        "⭕️به بخش تنظیمات لغو سفارش خوش آمدید\n\n"
        "✅با استفاده از تنظیمات این بخش میتوانید لغو سفارشات توسط کاربر را کنترل نمایید\n\n"
        "👈جهت تنظیم هر آیتم گزینه مورد نظر را بزنید",
        reply_markup=inline([
            [("وضعیت: " + ("✅فعال" if cond == "on" else "❌غیر فعال"), "acan_toggle")],
            [(f"حداقل مجاز: {min_members}", "acan_min"), ("⌛️مدت زمان: " + f"{wait_seconds} ثانیه", "acan_wait")],
            [(f"ضریب بازگشت: {refund_ratio}", "acan_ratio")],
            [("🔙 بازگشت به پنل مدیریت", "acan_back")],
        ])
    )


async def acan_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    if state == "acan_min":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting("cancel_min_members", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    if state == "acan_wait":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting("cancel_wait_seconds", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    if state == "acan_ratio":
        try:
            val = float(text)
        except ValueError:
            await update.message.reply_text("❌ فقط عدد اعشاری مجاز است (مثلاً 0.5).")
            return True
        set_setting("cancel_refund_ratio", str(val))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    return False


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data == "acan_toggle":
        await q.answer()
        current = get_setting("cancel_enabled", "on")
        set_setting("cancel_enabled", "off" if current == "on" else "on")
        await cancel_menu(update, context)
        return True
    if data == "acan_min":
        await q.answer()
        set_user_state(q.from_user.id, "acan_min")
        await q.message.reply_text("حداقل تعداد ممبر مجاز برای لغو سفارش را ارسال کنید:", reply_markup=back_button())
        return True
    if data == "acan_wait":
        await q.answer()
        set_user_state(q.from_user.id, "acan_wait")
        await q.message.reply_text("چند ثانیه پس از ثبت سفارش کاربر میتواند لغو کند؟", reply_markup=back_button())
        return True
    if data == "acan_ratio":
        await q.answer()
        set_user_state(q.from_user.id, "acan_ratio")
        await q.message.reply_text("ضریب بازگشت سکه (مثلاً 0.5) را ارسال کنید:", reply_markup=back_button())
        return True
    if data == "acan_back":
        await acan_back(update, context)
        return True
    return False
