from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from bot_manager import is_admin, set_user_state, get_user_state
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_valid_username


async def channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    await update.message.reply_text(
        "گزینه مورد نظر را انتخاب کنید",
        reply_markup=inline([
            [("📋 تنظیم کانال تبلیغات", "ach_set_ads")],
            [("🎁 تنظیم کانال کد هدیه", "ach_set_gift")],
            [("🔐 کانال جوین اجباری اول", "ach_set_force1")],
            [("🔐 کانال جوین اجباری دوم", "ach_set_force2")],
            [("🔙 بازگشت به پنل مدیریت", "ach_back")],
        ])
    )


async def ach_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


# ==================== State Handler ====================
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
    
    if state == "ach_set_ads":
        channel = text.lstrip("@").strip()
        if not is_valid_username(channel):
            await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
            return True
        
        from database import db
        with db.conn() as c:
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("ads_channel", channel))
        
        # ذخیره در فایل (چون Config.ADS_CHANNEL از env میاد)
        try:
            with open("lib/kodam/channel_ads.txt", "w") as f:
                f.write(channel)
        except Exception:
            pass
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"کانال تبلیغات به @{channel} تنظیم شد",
            reply_markup=admin_panel()
        )
        return True
    
    if state == "ach_set_gift":
        channel = text.lstrip("@").strip()
        if not is_valid_username(channel):
            await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
            return True
        
        from database import db
        with db.conn() as c:
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("gift_channel", channel))
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"کانال کد هدیه به @{channel} تنظیم شد",
            reply_markup=admin_panel()
        )
        return True
    
    if state == "ach_set_force1":
        channel = text.lstrip("@").strip()
        if not is_valid_username(channel):
            await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
            return True
        
        from database import db
        with db.conn() as c:
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("force_channel_1", channel))
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"کانال جوین اجباری اول به @{channel} تنظیم شد",
            reply_markup=admin_panel()
        )
        return True
    
    if state == "ach_set_force2":
        channel = text.lstrip("@").strip()
        if not is_valid_username(channel):
            await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
            return True
        
        from database import db
        with db.conn() as c:
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("force_channel_2", channel))
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"کانال جوین اجباری دوم به @{channel} تنظیم شد",
            reply_markup=admin_panel()
        )
        return True
    
    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data == "ach_set_ads":
        await q.answer()
        set_user_state(q.from_user.id, "ach_set_ads")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            q.from_user.id,
            "آیدی کانال تبلیغات را ارسال کنید (بدون @):",
            reply_markup=back_button()
        )
        return True
    if data == "ach_set_gift":
        await q.answer()
        set_user_state(q.from_user.id, "ach_set_gift")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            q.from_user.id,
            "آیدی کانال کد هدیه را ارسال کنید (بدون @):",
            reply_markup=back_button()
        )
        return True
    if data == "ach_set_force1":
        await q.answer()
        set_user_state(q.from_user.id, "ach_set_force1")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            q.from_user.id,
            "آیدی کانال جوین اجباری اول را ارسال کنید (بدون @):",
            reply_markup=back_button()
        )
        return True
    if data == "ach_set_force2":
        await q.answer()
        set_user_state(q.from_user.id, "ach_set_force2")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            q.from_user.id,
            "آیدی کانال جوین اجباری دوم را ارسال کنید (بدون @):",
            reply_markup=back_button()
        )
        return True
    if data == "ach_back":
        await ach_back(update, context)
        return True
    return False
