from telegram import Update
from telegram.ext import ContextTypes
from bot_manager import is_admin, set_user_state, get_user_state, set_setting, get_setting
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int


async def transfer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    
    cond = get_setting("transfer_enabled", "on")
    report = get_setting("transfer_report", "on")
    min_tr = get_setting("transfer_min", "10")
    max_tr = get_setting("transfer_max", "1000")
    
    await update.message.reply_text(
        "⭕️به بخش تنظیمات انتقال سکه خوش آمدید\n\n"
        "✅با استفاده از تنظیمات این بخش میتوانید انتقالات سکه توسط کاربر را کنترل نمایید\n\n"
        "👈جهت تنظیم هر آیتم گزینه مورد نظر را بزنید",
        reply_markup=inline([
            [("وضعیت: " + ("✅فعال" if cond == "on" else "❌غیر فعال"), "atr_toggle")],
            [("گزارش: " + ("✅فعال" if report == "on" else "❌غیر فعال"), "atr_report")],
            [(f"حداقل: {min_tr}", "atr_min"), (f"حداکثر: {max_tr}", "atr_max")],
            [("🔙 بازگشت به پنل مدیریت", "atr_back")],
        ])
    )


async def atr_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    if state == "atr_min":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting("transfer_min", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    if state == "atr_max":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting("transfer_max", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    return False


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data == "atr_toggle":
        await q.answer()
        current = get_setting("transfer_enabled", "on")
        set_setting("transfer_enabled", "off" if current == "on" else "on")
        await transfer_menu(update, context)
        return True
    if data == "atr_report":
        await q.answer()
        current = get_setting("transfer_report", "on")
        set_setting("transfer_report", "off" if current == "on" else "on")
        await transfer_menu(update, context)
        return True
    if data == "atr_min":
        await q.answer()
        set_user_state(q.from_user.id, "atr_min")
        await q.message.reply_text("حداقل انتقال را ارسال کنید:", reply_markup=back_button())
        return True
    if data == "atr_max":
        await q.answer()
        set_user_state(q.from_user.id, "atr_max")
        await q.message.reply_text("حداکثر انتقال را ارسال کنید:", reply_markup=back_button())
        return True
    if data == "atr_back":
        await atr_back(update, context)
        return True
    return False
