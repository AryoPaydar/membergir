from telegram import Update
from telegram.ext import ContextTypes
from bot_manager import is_admin, set_setting, get_setting
from utils.keyboards import inline, back_button, admin_panel


async def complete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    
    current = get_setting("takmil_ads", "off")
    status = "✅ فعال" if current == "on" else "❌ غیر فعال"
    
    await update.message.reply_text(
        "✅ با استفاده از تنظیمات این بخش می توانید به سفارشات موجود در کانال تبلیغات پایان بدهید\n\n"
        "⚠️در صورتی که این بخش فعال باشد ادمین اصلی ربات می تواند با زدن دکمه گزارش تخلف در زیر هر تبلیغ ، به آن تبلیغ پایان دهد",
        reply_markup=inline([
            [(status, "acomplete_toggle")],
            [("🔙 بازگشت به پنل مدیریت", "acomplete_back")],
        ])
    )


async def acomplete_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data == "acomplete_toggle":
        await q.answer()
        current = get_setting("takmil_ads", "off")
        set_setting("takmil_ads", "off" if current == "on" else "on")
        new_status = "✅ فعال" if current == "off" else "❌ غیر فعال"
        try:
            await q.message.edit_reply_markup(
                reply_markup=inline([
                    [(new_status, "acomplete_toggle")],
                    [("🔙 بازگشت به پنل مدیریت", "acomplete_back")],
                ])
            )
        except Exception:
            pass
        return True
    
    if data == "acomplete_back":
        await acomplete_back(update, context)
        return True
    
    return False
