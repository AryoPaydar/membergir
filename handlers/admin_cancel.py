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
    min_members = get_setting("cancel_min_members", "0")
    wait_minutes = get_setting("cancel_wait_minutes", "0")

    if min_members == "0":
        min_members_display = "00 (بدون محدودیت)"
    else:
        min_members_display = min_members

    if wait_minutes == "0":
        wait_display = "00 (فوری)"
    else:
        wait_display = f"{wait_minutes} دقیقه"

    await update.message.reply_text(
        "⭕️به بخش تنظیمات لغو سفارش خوش آمدید\n\n"
        "✅با استفاده از تنظیمات این بخش میتوانید لغو سفارشات توسط کاربر را کنترل نمایید\n\n"
        "👈جهت تنظیم هر آیتم گزینه مورد نظر را بزنید",
        reply_markup=inline([
            [("وضعیت: " + ("✅فعال" if cond == "on" else "❌غیر فعال"), "acan_toggle")],
            [(f"حداقل مجاز: {min_members_display}", "acan_min"),
             (f"⌛️مدت زمان: {wait_display}", "acan_wait")],
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
        # 00 یعنی بدون محدودیت
        if text == "00":
            set_setting("cancel_min_members", "0")
            set_user_state(user_id, "none")
            await update.message.reply_text(
                "✅ حداقل تعداد ممبر: بدون محدودیت (00)",
                reply_markup=admin_panel()
            )
            return True
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است (یا 00 برای بدون محدودیت).")
            return True
        set_setting("cancel_min_members", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True

    if state == "acan_wait":
        # 00 یعنی فوری
        if text == "00":
            set_setting("cancel_wait_minutes", "0")
            set_user_state(user_id, "none")
            await update.message.reply_text(
                "✅ مدت زمان انتظار: فوری (00)",
                reply_markup=admin_panel()
            )
            return True
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است (یا 00 برای فوری).")
            return True
        set_setting("cancel_wait_minutes", text)
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
        await q.message.reply_text(
            "حداقل تعداد ممبر مجاز برای لغو سفارش را ارسال کنید:\n\n"
            "⚠️ ارسال 00 یعنی بدون محدودیت",
            reply_markup=back_button()
        )
        return True
    if data == "acan_wait":
        await q.answer()
        set_user_state(q.from_user.id, "acan_wait")
        await q.message.reply_text(
            "چند دقیقه پس از ثبت سفارش کاربر میتواند سفارش خود را لغو کند؟\n\n"
            "⚠️ ارسال 00 یعنی فوری (بدون انتظار)",
            reply_markup=back_button()
        )
        return True
    if data == "acan_back":
        await acan_back(update, context)
        return True
    return False
