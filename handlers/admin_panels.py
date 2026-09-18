from telegram import Update
from telegram.ext import ContextTypes
from bot_manager import is_admin, set_user_state, get_user_state, set_setting, get_setting
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int


async def panels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    await update.message.reply_text(
        "✅در این بخش می توانید پنل های کاربری ربات را تنظیم‌نمایید",
        reply_markup=inline([
            [("👤 عضویت عادی", "apl_normal_join"), ("👥 زیرمجموعه عادی", "apl_normal_ref")],
            [("👤 عضویت حرفه‌ای", "apl_pro_join"), ("👥 زیرمجموعه حرفه‌ای", "apl_pro_ref")],
            [("👤 عضویت ویژه", "apl_vip_join"), ("👥 زیرمجموعه ویژه", "apl_vip_ref")],
            [("💰 سکه روزانه عادی", "apl_normal_daily"), ("💰 سکه روزانه حرفه‌ای", "apl_pro_daily")],
            [("💰 سکه روزانه ویژه", "apl_vip_daily")],
            [("🔙 بازگشت به پنل مدیریت", "apl_back")],
        ])
    )


async def apl_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    if state.startswith("apl_set_"):
        key = state.replace("apl_set_", "")
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_setting(f"panel_{key}", text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ با موفقیت تنظیم شد.", reply_markup=admin_panel())
        return True
    
    return False


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    mapping = {
        "apl_normal_join": ("normal_join_coin", "سکه عضویت پنل عادی را وارد کنید:"),
        "apl_normal_ref": ("normal_invite_coin", "سکه زیرمجموعه پنل عادی را وارد کنید:"),
        "apl_pro_join": ("pro_join_coin", "سکه عضویت پنل حرفه‌ای را وارد کنید:"),
        "apl_pro_ref": ("pro_invite_coin", "سکه زیرمجموعه پنل حرفه‌ای را وارد کنید:"),
        "apl_vip_join": ("vip_join_coin", "سکه عضویت پنل ویژه را وارد کنید:"),
        "apl_vip_ref": ("vip_invite_coin", "سکه زیرمجموعه پنل ویژه را وارد کنید:"),
        "apl_normal_daily": ("normal_daily", "سکه روزانه پنل عادی را وارد کنید:"),
        "apl_pro_daily": ("pro_daily", "سکه روزانه پنل حرفه‌ای را وارد کنید:"),
        "apl_vip_daily": ("vip_daily", "سکه روزانه پنل ویژه را وارد کنید:"),
    }
    
    if data in mapping:
        await q.answer()
        key, msg = mapping[data]
        set_user_state(q.from_user.id, f"apl_set_{key}")
        await q.message.reply_text(msg, reply_markup=back_button())
        return True
    
    if data == "apl_back":
        await apl_back(update, context)
        return True
    return False
