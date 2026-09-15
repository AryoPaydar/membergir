from telegram import Update
from telegram.ext import ContextTypes
from bot_manager import is_admin, set_user_state, get_user_state, get_setting, set_setting
from utils.keyboards import inline, admin_panel

# ==================== منوی متن‌ها ====================
async def texts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "📇 <b>تنظیم متن‌ها</b>\n\nکدام متن را ویرایش می‌کنید؟",
        parse_mode="HTML",
        reply_markup=inline([
            [("متن استارت", "admin_set_text:start_text")],
            [("متن بنر زیرمجموعه", "admin_set_text:referral_text")],
            [("متن قوانین", "admin_set_text:rules_text")],
            [("متن خاموشی ربات", "admin_set_text:power_text")],
            [("متن راهنمای /help", "admin_set_text:help_text")],
            [("متن سفارش ممبر", "admin_set_text:order_intro_text")],
            [("🔙 بازگشت", "admin_back")],
        ])
    )

# ==================== ویرایش متن ====================
async def edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    key = q.data.split(":", 1)[1]
    current = get_setting(key, "(خالی)")
    set_user_state(q.from_user.id, "admin_edit_text", {"key": key})
    await q.message.edit_text(
        f"📝 <b>متن فعلی:</b>\n\n<code>{current}</code>\n\n"
        f"متن جدید را ارسال کنید:",
        parse_mode="HTML"
    )

# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    state, data = get_user_state(user_id)
    if state != "admin_edit_text":
        return False
    
    key = data.get("key")
    if not key:
        set_user_state(user_id, "none")
        return True
    
    new_text = update.message.text or update.message.caption or ""
    if not new_text:
        await update.message.reply_text("❌ متن خالی مجاز نیست.")
        return True
    
    set_setting(key, new_text)
    set_user_state(user_id, "none")
    await update.message.reply_text("✅ متن ذخیره شد.", reply_markup=admin_panel())
    return True

# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    if data.startswith("admin_set_text:"):
        await edit_text_start(update, context)
        return True
    return False