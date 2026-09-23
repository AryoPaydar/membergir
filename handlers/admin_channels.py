from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    is_admin, set_user_state, get_user_state, get_setting, set_setting
)
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_valid_username, normalize_channel
from datetime import datetime
import jdatetime


# ==================== منوی تنظیم کانال ====================
async def channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    await update.message.reply_text(
        "گزینه مورد نظر را انتخاب کنید",
        reply_markup=inline([
            [("📋 تنظیم کانال تبلیغات", "ach_set_ads")],
            [("🎁 تنظیم کانال کد هدیه", "ach_set_gift")],
            [("🎗 کانال اسپانسر", "ach_sponsor_menu")],
            [("🚫 کانال های ممنوعه", "ach_banned_menu")],
            [("📢 کانال Ads", "ach_ads_menu")],
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


# ==================== چک کانال معتبر ====================
def _is_valid_channel_id(text: str) -> tuple:
    """چک میکنه که ورودی معتبره — برمیگردونه (valid, channel)"""
    text = text.strip()
    
    # حالت 1: @channel
    if text.startswith("@"):
        ch = text[1:].strip()
        if is_valid_username(ch):
            return True, ch
    
    # حالت 2: https://t.me/+XXXX یا https://t.me/XXXX
    if text.startswith("https://t.me/") or text.startswith("t.me/") or text.startswith("http://t.me/"):
        # استخراج بخش بعد از t.me/
        for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
            if text.startswith(prefix):
                ch = text[len(prefix):].strip()
                if ch:
                    return True, ch
    
    return False, ""


def _format_jalali_date(created_at):
    try:
        dt = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S")
        return jdatetime.date.fromgregorian(date=dt.date()).strftime("%Y/%m/%d")
    except Exception:
        return str(created_at)[:10]


# ==================== State Handler — تنظیم کانال‌های تبلیغات/هدیه/جوین ====================
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
    
    # ==== تنظیم کانال تبلیغات ====
    if state == "ach_set_ads":
        channel = text.lstrip("@").strip()
        if not is_valid_username(channel):
            await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
            return True
        set_setting("ads_channel", channel)
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"کانال تبلیغات به @{channel} تنظیم شد",
            reply_markup=admin_panel()
        )
        return True
    
    # ==== تنظیم کانال کد هدیه ====
    if state == "ach_set_gift":
        channel = text.lstrip("@").strip()
        if not is_valid_username(channel):
            await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
            return True
        set_setting("gift_channel", channel)
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"کانال کد هدیه به @{channel} تنظیم شد",
            reply_markup=admin_panel()
        )
        return True
    
    # ==== افزودن کانال اسپانسر ====
    if state == "ach_sponsor_add":
        valid, channel = _is_valid_channel_id(text)
        if not valid:
            await update.message.reply_text(
                "❌ آیدی نامعتبر.\n\n"
                "فرمت‌های مجاز:\n"
                "@dorv\n"
                "https://t.me/+RF3WEHVqJAYwNTM0"
            )
            return True
        
        with db.conn() as c:
            try:
                c.execute("INSERT INTO sponsor_channels (channel) VALUES (?)", (channel,))
            except Exception:
                await update.message.reply_text("❌ این کانال قبلاً اضافه شده است.")
                set_user_state(user_id, "none")
                return True
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            "کانال / گروه ارسالی با موفقیت به اسپانسر اضافه شد",
            reply_markup=admin_panel()
        )
        return True
    
    # ==== افزودن کانال ممنوعه ====
    if state == "ach_banned_add":
        valid, channel = _is_valid_channel_id(text)
        if not valid:
            await update.message.reply_text(
                "❌ آیدی نامعتبر.\n\n"
                "فرمت مجاز:\n"
                "@dorv"
            )
            return True
        
        with db.conn() as c:
            try:
                c.execute("INSERT INTO banned_channels (channel) VALUES (?)", (channel,))
            except Exception:
                await update.message.reply_text("❌ این کانال قبلاً اضافه شده است.")
                set_user_state(user_id, "none")
                return True
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            "کانال / گروه ارسالی با موفقیت به ممنوعه اضافه شد",
            reply_markup=admin_panel()
        )
        return True
    
    return False


# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    # ==== تنظیم کانال تبلیغات ====
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
    
    # ==== تنظیم کانال کد هدیه ====
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
    
    if data == "ach_back":
        await ach_back(update, context)
        return True
    
    # ============ کانال اسپانسر ============
    if data == "ach_sponsor_menu":
        await q.answer()
        with db.conn() as c:
            chs = c.execute("SELECT * FROM sponsor_channels ORDER BY id DESC").fetchall()
        
        if not chs:
            await q.message.edit_text(
                "🎗 کانال های اسپانسر :\n\n"
                "❌ هنوز کانالی اضافه نشده است.",
                reply_markup=inline([
                    [("➕ افزودن کانال", "ach_sponsor_add_btn")],
                    [("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")],
                ])
            )
            return True
        
        rows = []
        for ch in chs:
            rows.append([
                (f"📢 {ch['channel']}", f"ach_sponsor_view:{ch['id']}")
            ])
        rows.append([("➕ افزودن کانال", "ach_sponsor_add_btn")])
        rows.append([("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")])
        
        try:
            await q.message.edit_text(
                f"🎗 کانال های اسپانسر :\n\n👥 تعداد : {len(chs)} کانال",
                reply_markup=inline(rows)
            )
        except Exception:
            pass
        return True
    
    if data == "ach_sponsor_add_btn":
        await q.answer()
        set_user_state(q.from_user.id, "ach_sponsor_add")
        await q.message.edit_text(
            "آیدی کانال اسپانسر مد نظر خود را وارد نمایید\n\n"
            "فرمت‌های مجاز:\n"
            "@dorv\n"
            "https://t.me/+RF3WEHVqJAYwNTM0",
            reply_markup=inline([[("🔙 بازگشت", "ach_sponsor_menu")]])
        )
        return True
    
    if data.startswith("ach_sponsor_view:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        
        with db.conn() as c:
            ch = c.execute("SELECT * FROM sponsor_channels WHERE id = ?", (ch_id,)).fetchone()
        
        if not ch:
            await q.message.edit_text(
                "❌ کانال یافت نشد.",
                reply_markup=inline([[("🔙 بازگشت", "ach_sponsor_menu")]])
            )
            return True
        
        ch = dict(ch)
        date_jalali = _format_jalali_date(ch["created_at"])
        
        await q.message.edit_text(
            f"📢 <b>مشخصات کانال اسپانسر</b>\n\n"
            f"نام کانال : {ch['channel']}\n"
            f"آیدی کانال : @{ch['channel']}\n"
            f"زمان ثبت کانال : {date_jalali}",
            parse_mode="HTML",
            reply_markup=inline([
                [("🗑 حذف", f"ach_sponsor_del:{ch_id}")],
                [("🔙 بازگشت", "ach_sponsor_menu")],
            ])
        )
        return True
    
    if data.startswith("ach_sponsor_del:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        
        with db.conn() as c:
            ch = c.execute("SELECT channel FROM sponsor_channels WHERE id = ?", (ch_id,)).fetchone()
            if ch:
                c.execute("DELETE FROM sponsor_channels WHERE id = ?", (ch_id,))
        
        if ch:
            await q.answer(f"کانال {ch['channel']} با موفقیت حذف شد", show_alert=True)
        else:
            await q.answer("❌ کانال یافت نشد.", show_alert=True)
        
        # بازگشت به لیست
        q.data = "ach_sponsor_menu"
        await handle_callback(update, context)
        return True
    
    # ============ کانال ممنوعه ============
    if data == "ach_banned_menu":
        await q.answer()
        with db.conn() as c:
            chs = c.execute("SELECT * FROM banned_channels ORDER BY id DESC").fetchall()
        
        if not chs:
            await q.message.edit_text(
                "🚫 کانال های ممنوعه :\n\n"
                "❌ هنوز کانالی اضافه نشده است.",
                reply_markup=inline([
                    [("➕ افزودن کانال", "ach_banned_add_btn")],
                    [("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")],
                ])
            )
            return True
        
        rows = []
        for ch in chs:
            rows.append([
                (f"🚫 {ch['channel']}", f"ach_banned_view:{ch['id']}")
            ])
        rows.append([("➕ افزودن کانال", "ach_banned_add_btn")])
        rows.append([("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")])
        
        try:
            await q.message.edit_text(
                f"🚫 کانال های ممنوعه :\n\n👥 تعداد : {len(chs)} کانال",
                reply_markup=inline(rows)
            )
        except Exception:
            pass
        return True
    
    if data == "ach_banned_add_btn":
        await q.answer()
        set_user_state(q.from_user.id, "ach_banned_add")
        await q.message.edit_text(
            "آیدی کانال ممنوعه مد نظر خود را وارد نمایید\n\n"
            "فرمت مجاز:\n"
            "@dorv",
            reply_markup=inline([[("🔙 بازگشت", "ach_banned_menu")]])
        )
        return True
    
    if data.startswith("ach_banned_view:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        
        with db.conn() as c:
            ch = c.execute("SELECT * FROM banned_channels WHERE id = ?", (ch_id,)).fetchone()
        
        if not ch:
            await q.message.edit_text(
                "❌ کانال یافت نشد.",
                reply_markup=inline([[("🔙 بازگشت", "ach_banned_menu")]])
            )
            return True
        
        ch = dict(ch)
        date_jalali = _format_jalali_date(ch["created_at"])
        
        await q.message.edit_text(
            f"🚫 <b>مشخصات کانال ممنوعه</b>\n\n"
            f"آیدی کانال : @{ch['channel']}\n"
            f"زمان ثبت کانال : {date_jalali}",
            parse_mode="HTML",
            reply_markup=inline([
                [("🗑 حذف", f"ach_banned_del:{ch_id}")],
                [("🔙 بازگشت", "ach_banned_menu")],
            ])
        )
        return True
    
    if data.startswith("ach_banned_del:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        
        with db.conn() as c:
            ch = c.execute("SELECT channel FROM banned_channels WHERE id = ?", (ch_id,)).fetchone()
            if ch:
                c.execute("DELETE FROM banned_channels WHERE id = ?", (ch_id,))
        
        if ch:
            await q.answer(f"کانال {ch['channel']} با موفقیت حذف شد", show_alert=True)
        else:
            await q.answer("❌ کانال یافت نشد.", show_alert=True)
        
        q.data = "ach_banned_menu"
        await handle_callback(update, context)
        return True
    
    # ============ بازگشت به منوی تنظیم کانال ============
    if data == "ach_channels_menu":
        await q.answer()
        try:
            await q.message.edit_text(
                "گزینه مورد نظر را انتخاب کنید",
                reply_markup=inline([
                    [("📋 تنظیم کانال تبلیغات", "ach_set_ads")],
                    [("🎁 تنظیم کانال کد هدیه", "ach_set_gift")],
                    [("🎗 کانال اسپانسر", "ach_sponsor_menu")],
                    [("🚫 کانال های ممنوعه", "ach_banned_menu")],
                    [("📢 کانال Ads", "ach_ads_menu")],
                    [("🔙 بازگشت به پنل مدیریت", "ach_back")],
                ])
            )
        except Exception:
            pass
        return True
    
    # ============ کانال Ads — پاس به admin_ads_channels ============
    if data == "ach_ads_menu" or data.startswith("aads_"):
        from handlers import admin_ads_channels
        return await admin_ads_channels.handle_callback(update, context)
    
    return False
