from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import is_admin, set_user_state, get_user_state
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int, is_valid_username
from datetime import datetime
import jdatetime


def _is_valid_channel_id(text: str) -> tuple:
    """چک میکنه که ورودی معتبره — برمیگردونه (valid, channel)"""
    text = text.strip()
    
    if text.startswith("@"):
        ch = text[1:].strip()
        if is_valid_username(ch):
            return True, ch
    
    if text.startswith("https://t.me/") or text.startswith("t.me/") or text.startswith("http://t.me/"):
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


# ==================== منوی کانال Ads ====================
async def ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    
    with db.conn() as c:
        chs = c.execute("SELECT * FROM ads_channels ORDER BY position, id").fetchall()
    
    if not chs:
        await update.message.reply_text(
            "📢 کانال های Ads :\n\n"
            "❌ هنوز کانالی اضافه نشده است.\n\n"
            "💡 نکته: کانال Ads کانالیه که به جای «👤 سفارش {members} ممبر» در پست تبلیغات نمایش داده میشه.",
            reply_markup=inline([
                [("➕ افزودن کانال", "aads_add_btn")],
                [("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")],
            ])
        )
        return
    
    rows = []
    for ch in chs:
        remaining_text = "نامحدود" if ch["remaining"] == 0 else f"{ch['remaining']} بار"
        rows.append([
            (f"📢 {ch['display_name']} ({remaining_text})", f"aads_view:{ch['id']}")
        ])
    rows.append([("➕ افزودن کانال", "aads_add_btn")])
    rows.append([("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")])
    
    await update.message.reply_text(
        f"📢 کانال های Ads :\n\n👥 تعداد : {len(chs)} کانال",
        reply_markup=inline(rows)
    )


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
    
    # ==== مرحله ۱: دریافت لینک/آیدی کانال ====
    if state == "aads_add_channel":
        valid, channel = _is_valid_channel_id(text)
        if not valid:
            await update.message.reply_text(
                "❌ آیدی نامعتبر.\n\n"
                "فرمت‌های مجاز:\n"
                "@dorv\n"
                "https://t.me/+RF3WEHVqJAYwNTM0"
            )
            return True
        
        set_user_state(user_id, "aads_add_name", {"channel": channel})
        await update.message.reply_text(
            "✅ کانال پذیرفته شد.\n\n"
            "حالا نام نمایشی که میخواید توی پست تبلیغات نمایش داده بشه رو وارد کنید:\n\n"
            "مثال:\n"
            "آکادمی زبان خوان",
            reply_markup=back_button()
        )
        return True
    
    # ==== مرحله ۲: دریافت نام نمایشی ====
    if state == "aads_add_name":
        if not text or len(text) > 50:
            await update.message.reply_text("❌ نام نمایشی نامعتبر (حداکثر ۵۰ کاراکتر).")
            return True
        
        channel = data.get("channel")
        set_user_state(user_id, "aads_add_count", {"channel": channel, "display_name": text})
        await update.message.reply_text(
            "✅ نام نمایشی ثبت شد.\n\n"
            "حالا تعداد نمایش این کانال رو وارد کنید:\n\n"
            "🔹 اگه عدد وارد کنید (مثلاً 100): اون کانال 100 بار به جای دکمه سفارش نمایش داده میشه.\n"
            "🔹 اگه عدد 0 وارد کنید: تا زمانی که از لیست حذف نشه، همیشه نمایش داده میشه.",
            reply_markup=back_button()
        )
        return True
    
    # ==== مرحله ۳: دریافت تعداد ====
    if state == "aads_add_count":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        
        channel = data.get("channel")
        display_name = data.get("display_name")
        remaining = int(text)
        
        # موقعیت: آخرین + ۱
        with db.conn() as c:
            pos_row = c.execute("SELECT COALESCE(MAX(position), 0) as max_pos FROM ads_channels").fetchone()
            new_pos = (pos_row["max_pos"] or 0) + 1
            c.execute("""
                INSERT INTO ads_channels (channel, display_name, remaining, position)
                VALUES (?, ?, ?, ?)
            """, (channel, display_name, remaining, new_pos))
        
        set_user_state(user_id, "none")
        
        remaining_text = "نامحدود" if remaining == 0 else f"{remaining} بار"
        await update.message.reply_text(
            f"✅ کانال Ads با موفقیت اضافه شد:\n\n"
            f"📢 کانال : {channel}\n"
            f"🏷 نام نمایشی : {display_name}\n"
            f"🔢 تعداد نمایش : {remaining_text}",
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
    
    # ==== منوی Ads ====
    if data == "ach_ads_menu" or data == "aads_menu":
        await q.answer()
        
        with db.conn() as c:
            chs = c.execute("SELECT * FROM ads_channels ORDER BY position, id").fetchall()
        
        if not chs:
            try:
                await q.message.edit_text(
                    "📢 کانال های Ads :\n\n"
                    "❌ هنوز کانالی اضافه نشده است.",
                    reply_markup=inline([
                        [("➕ افزودن کانال", "aads_add_btn")],
                        [("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")],
                    ])
                )
            except Exception:
                pass
            return True
        
        rows = []
        for ch in chs:
            remaining_text = "نامحدود" if ch["remaining"] == 0 else f"{ch['remaining']} بار"
            rows.append([
                (f"📢 {ch['display_name']} ({remaining_text})", f"aads_view:{ch['id']}")
            ])
        rows.append([("➕ افزودن کانال", "aads_add_btn")])
        rows.append([("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")])
        
        try:
            await q.message.edit_text(
                f"📢 کانال های Ads :\n\n👥 تعداد : {len(chs)} کانال",
                reply_markup=inline(rows)
            )
        except Exception:
            pass
        return True
    
    # ==== افزودن کانال ====
    if data == "aads_add_btn":
        await q.answer()
        set_user_state(q.from_user.id, "aads_add_channel")
        await q.message.edit_text(
            "🔗 لینک یا آیدی کانال/گروه رو وارد کنید:\n\n"
            "فرمت‌های مجاز:\n"
            "@dorv\n"
            "https://t.me/+RF3WEHVqJAYwNTM0",
            reply_markup=inline([[("🔙 بازگشت", "aads_menu")]])
        )
        return True
    
    # ==== مشاهده کانال ====
    if data.startswith("aads_view:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        
        with db.conn() as c:
            ch = c.execute("SELECT * FROM ads_channels WHERE id = ?", (ch_id,)).fetchone()
        
        if not ch:
            await q.message.edit_text(
                "❌ کانال یافت نشد.",
                reply_markup=inline([[("🔙 بازگشت", "aads_menu")]])
            )
            return True
        
        ch = dict(ch)
        date_jalali = _format_jalali_date(ch["created_at"])
        remaining_text = "نامحدود" if ch["remaining"] == 0 else f"{ch['remaining']} بار"
        
        await q.message.edit_text(
            f"📢 <b>مشخصات کانال Ads</b>\n\n"
            f"🔗 کانال : {ch['channel']}\n"
            f"🏷 نام نمایشی : {ch['display_name']}\n"
            f"🔢 تعداد نمایش : {remaining_text}\n"
            f"📆 زمان ثبت : {date_jalali}",
            parse_mode="HTML",
            reply_markup=inline([
                [("✏️ ویرایش نام", f"aads_edit_name:{ch_id}"),
                 ("🔢 ویرایش تعداد", f"aads_edit_count:{ch_id}")],
                [("🗑 حذف کانال", f"aads_del:{ch_id}")],
                [("🔙 بازگشت", "aads_menu")],
            ])
        )
        return True
    
    # ==== ویرایش نام ====
    if data.startswith("aads_edit_name:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "aads_edit_name", {"ch_id": ch_id})
        await q.message.edit_text(
            "🏷 نام نمایشی جدید رو وارد کنید:",
            reply_markup=inline([[("🔙 بازگشت", f"aads_view:{ch_id}")]])
        )
        return True
    
    # ==== ویرایش تعداد ====
    if data.startswith("aads_edit_count:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "aads_edit_count", {"ch_id": ch_id})
        await q.message.edit_text(
            "🔢 تعداد نمایش جدید رو وارد کنید:\n\n"
            "🔹 عدد 0 = نامحدود",
            reply_markup=inline([[("🔙 بازگشت", f"aads_view:{ch_id}")]])
        )
        return True
    
    # ==== حذف کانال ====
    if data.startswith("aads_del:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        
        with db.conn() as c:
            ch = c.execute("SELECT display_name FROM ads_channels WHERE id = ?", (ch_id,)).fetchone()
            if ch:
                c.execute("DELETE FROM ads_channels WHERE id = ?", (ch_id,))
        
        if ch:
            await q.answer(f"کانال {ch['display_name']} با موفقیت حذف شد", show_alert=True)
        else:
            await q.answer("❌ کانال یافت نشد.", show_alert=True)
        
        q.data = "aads_menu"
        await handle_callback(update, context)
        return True
    
    return False


# ==================== State Handler اضافه برای ویرایش ====================
async def handle_state_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """هندل ویرایش نام/تعداد کانال Ads"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if state == "aads_edit_name":
        if not text or len(text) > 50:
            await update.message.reply_text("❌ نام نامعتبر (حداکثر ۵۰ کاراکتر).")
            return True
        
        ch_id = data.get("ch_id")
        with db.conn() as c:
            c.execute("UPDATE ads_channels SET display_name = ? WHERE id = ?", (text, ch_id))
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"✅ نام نمایشی ویرایش شد: {text}",
            reply_markup=admin_panel()
        )
        return True
    
    if state == "aads_edit_count":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        
        ch_id = data.get("ch_id")
        count = int(text)
        
        with db.conn() as c:
            c.execute("UPDATE ads_channels SET remaining = ? WHERE id = ?", (count, ch_id))
        
        set_user_state(user_id, "none")
        remaining_text = "نامحدود" if count == 0 else f"{count} بار"
        await update.message.reply_text(
            f"✅ تعداد نمایش ویرایش شد: {remaining_text}",
            reply_markup=admin_panel()
        )
        return True
    
    return False


# ==================== تابع کمکی برای ads.py ====================
def get_next_ads_channel():
    """
    کانال Ads بعدی رو برمیگردونه (برای نمایش در پست تبلیغات).
    الگوریتم:
    1. کانال‌هایی که remaining = 0 (نامحدود) یا remaining > 0 رو به ترتیب position برمیگردونه
    2. اگه همه remaining > 0 داشتن، یکی از اونها رو انتخاب و remaining رو کم میکنه
    3. اگه هیچ کانالی نبود، None برمیگردونه
    """
    with db.conn() as c:
        # همه کانال‌ها به ترتیب position
        chs = c.execute("SELECT * FROM ads_channels ORDER BY position, id").fetchall()
        
        if not chs:
            return None
        
        chs = [dict(ch) for
