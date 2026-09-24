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
    text = text.strip()
    if text.startswith("@"):
        ch = text[1:].strip()
        if is_valid_username(ch):
            return True, ch
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if text.startswith(prefix):
            ch = text[len(prefix):].strip()
            if ch:
                return True, ch
    return False, ""


def _format_jalali_date(created_at):
    try:
        dt = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S")
        return jdatetime.datetime.fromgregorian(datetime=dt).strftime("%Y/%m/%d %H:%M")
    except Exception:
        return str(created_at)[:16]


def _parse_count(text):
    """
    - "0"  → ('delete', 0)      حذف از لیست
    - "00" → ('unlimited', -1)  نامحدود
    - عدد  → ('limited', N)     تعداد محدود
    - None → (None, None)       نامعتبر
    """
    text = text.strip()
    if text == "00":
        return "unlimited", -1
    if text == "0":
        return "delete", 0
    if text.isdigit():
        return "limited", int(text)
    return None, None


# ==================== منوی Ads ====================
async def ads_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")

    with db.conn() as c:
        chs = c.execute("SELECT * FROM ads_channels ORDER BY position, id").fetchall()

    if not chs:
        await update.message.reply_text(
            "📢 کانال های Ads :\n\n❌ هنوز کانالی اضافه نشده است.",
            reply_markup=inline([
                [("➕ افزودن کانال", "aads_add_btn")],
                [("🔙 بازگشت به تنظیم کانال", "ach_channels_menu")],
            ])
        )
        return

    rows = []
    for ch in chs:
        remaining_text = "نامحدود" if ch["remaining"] == -1 else f"{ch['remaining']} بار"
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

    # مرحله ۱: لینک/آیدی
    if state == "aads_add_channel":
        valid, channel = _is_valid_channel_id(text)
        if not valid:
            await update.message.reply_text(
                "❌ آیدی نامعتبر.\n\nفرمت‌های مجاز:\n@dorv\nhttps://t.me/+RF3WEHVqJAYwNTM0"
            )
            return True
        set_user_state(user_id, "aads_add_name", {"channel": channel})
        await update.message.reply_text(
            "✅ کانال پذیرفته شد.\n\nحالا نام نمایشی که میخواید توی پست تبلیغات نمایش داده بشه رو وارد کنید:",
            reply_markup=back_button()
        )
        return True

    # مرحله ۲: نام نمایشی
    if state == "aads_add_name":
        if not text or len(text) > 50:
            await update.message.reply_text("❌ نام نمایشی نامعتبر (حداکثر ۵۰ کاراکتر).")
            return True
        set_user_state(user_id, "aads_add_count", {**data, "display_name": text})
        await update.message.reply_text(
            "✅ نام نمایشی ثبت شد.\n\n"
            "🔢 تعداد نمایش رو وارد کنید:\n"
            "• عدد مثبت (مثل 100): 100 بار نمایش داده میشه\n"
            "• 00 : نامحدود (تا زمان حذف دستی)\n"
            "• 0 : از لیست Ads حذف میشه",
            reply_markup=back_button()
        )
        return True

    # مرحله ۳: تعداد
    if state == "aads_add_count":
        kind, count = _parse_count(text)
        if kind is None:
            await update.message.reply_text("❌ فقط عدد مجاز است (0، 00 یا عدد مثبت).")
            return True

        if kind == "delete":
            await update.message.reply_text(
                "❌ برای افزودن نمی‌توانید 0 بفرستید. از 00 برای نامحدود استفاده کنید.",
                reply_markup=back_button()
            )
            return True

        channel = data.get("channel")
        display_name = data.get("display_name")
        remaining = count  # -1 = نامحدود، عدد مثبت = محدود

        with db.conn() as c:
            pos_row = c.execute("SELECT COALESCE(MAX(position), 0) as max_pos FROM ads_channels").fetchone()
            new_pos = (pos_row["max_pos"] or 0) + 1
            try:
                c.execute("""
                    INSERT INTO ads_channels (channel, display_name, remaining, position)
                    VALUES (?, ?, ?, ?)
                """, (channel, display_name, remaining, new_pos))
            except Exception:
                await update.message.reply_text("❌ این کانال قبلاً اضافه شده است.")
                set_user_state(user_id, "none")
                return True

        set_user_state(user_id, "none")
        remaining_text = "نامحدود" if remaining == -1 else f"{remaining} بار"
        await update.message.reply_text(
            f"✅ کانال Ads با موفقیت اضافه شد:\n\n"
            f"📢 کانال : {channel}\n"
            f"🏷 نام نمایشی : {display_name}\n"
            f"🔢 تعداد نمایش : {remaining_text}",
            reply_markup=admin_panel()
        )
        return True

    # ویرایش نام
    if state == "aads_edit_name":
        if not text or len(text) > 50:
            await update.message.reply_text("❌ نام نامعتبر (حداکثر ۵۰ کاراکتر).")
            return True
        ch_id = data.get("ch_id")
        with db.conn() as c:
            c.execute("UPDATE ads_channels SET display_name = ? WHERE id = ?", (text, ch_id))
        set_user_state(user_id, "none")
        await update.message.reply_text(f"✅ نام نمایشی ویرایش شد: {text}", reply_markup=admin_panel())
        return True

    # ویرایش تعداد
    if state == "aads_edit_count":
        kind, count = _parse_count(text)
        if kind is None:
            await update.message.reply_text("❌ فقط عدد مجاز است (0، 00 یا عدد مثبت).")
            return True

        ch_id = data.get("ch_id")

        if kind == "delete":
            with db.conn() as c:
                c.execute("DELETE FROM ads_channels WHERE id = ?", (ch_id,))
            set_user_state(user_id, "none")
            await update.message.reply_text(
                "✅ کانال از لیست Ads حذف شد.",
                reply_markup=admin_panel()
            )
            return True

        remaining = count
        with db.conn() as c:
            c.execute("UPDATE ads_channels SET remaining = ? WHERE id = ?", (remaining, ch_id))
        set_user_state(user_id, "none")
        remaining_text = "نامحدود" if remaining == -1 else f"{remaining} بار"
        await update.message.reply_text(f"✅ تعداد نمایش ویرایش شد: {remaining_text}", reply_markup=admin_panel())
        return True

    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False

    if data == "aads_menu":
        await q.answer()
        with db.conn() as c:
            chs = c.execute("SELECT * FROM ads_channels ORDER BY position, id").fetchall()

        if not chs:
            try:
                await q.message.edit_text(
                    "📢 کانال های Ads :\n\n❌ هنوز کانالی اضافه نشده است.",
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
            remaining_text = "نامحدود" if ch["remaining"] == -1 else f"{ch['remaining']} بار"
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

    if data == "aads_add_btn":
        await q.answer()
        set_user_state(q.from_user.id, "aads_add_channel")
        try:
            await q.message.edit_text(
                "🔗 لینک یا آیدی کانال/گروه رو وارد کنید:\n\nفرمت‌های مجاز:\n@dorv\nhttps://t.me/+RF3WEHVqJAYwNTM0",
                reply_markup=inline([[("🔙 بازگشت", "aads_menu")]])
            )
        except Exception:
            pass
        return True

    if data.startswith("aads_view:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        with db.conn() as c:
            ch = c.execute("SELECT * FROM ads_channels WHERE id = ?", (ch_id,)).fetchone()
        if not ch:
            await q.message.edit_text("❌ کانال یافت نشد.", reply_markup=inline([[("🔙 بازگشت", "aads_menu")]]))
            return True
        ch = dict(ch)
        date_jalali = _format_jalali_date(ch["created_at"])
        remaining_text = "نامحدود" if ch["remaining"] == -1 else f"{ch['remaining']} بار"
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

    if data.startswith("aads_edit_name:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "aads_edit_name", {"ch_id": ch_id})
        try:
            await q.message.edit_text(
                "🏷 نام نمایشی جدید رو وارد کنید:",
                reply_markup=inline([[("🔙 بازگشت", f"aads_view:{ch_id}")]])
            )
        except Exception:
            pass
        return True

    if data.startswith("aads_edit_count:"):
        await q.answer()
        ch_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "aads_edit_count", {"ch_id": ch_id})
        try:
            await q.message.edit_text(
                "🔢 تعداد نمایش جدید رو وارد کنید:\n\n"
                "• عدد مثبت (مثل 100): تعداد بار\n"
                "• 00 : نامحدود\n"
                "• 0 : حذف از لیست Ads",
                reply_markup=inline([[("🔙 بازگشت", f"aads_view:{ch_id}")]])
            )
        except Exception:
            pass
        return True

    if data.startswith("aads_del:"):
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


# ==================== تابع چرخشی برای ads.py ====================
def _notify_ads_complete(context, ch):
    """ارسال پیام تکمیل به ادمین — این تابع از ads.py صدا زده میشه"""
    pass  # پیام از داخل ads.py با await فرستاده میشه


def get_next_ads_channel(context=None):
    """
    الگوریتم چرخشی:
    - اگه remaining == -1 → نامحدود، همیشه میمونه
    - اگه remaining > 0 → یک واحد کم میشه
    - اگه remaining به 0 برسه → کانال حذف میشه + پیام تکمیل به ادمین
    """
    with db.conn() as c:
        chs = c.execute("""
            SELECT * FROM ads_channels
            ORDER BY last_shown_at ASC, position ASC
        """).fetchall()

        if not chs:
            return None

        ch = dict(chs[0])

        # اگه نامحدود → فقط last_shown_at آپدیت کن
        if ch["remaining"] == -1:
            c.execute("""
                UPDATE ads_channels SET last_shown_at = ? WHERE id = ?
            """, (int(datetime.now().timestamp()), ch["id"]))
            return ch

        # اگه محدود → یک واحد کم کن
        new_remaining = ch["remaining"] - 1

        if new_remaining <= 0:
            # پاک کردن کانال + نیاز به پیام تکمیل
            c.execute("DELETE FROM ads_channels WHERE id = ?", (ch["id"],))
            ch["_completed"] = True
            ch["_remaining_after"] = 0
        else:
            c.execute("""
                UPDATE ads_channels
                SET remaining = ?, last_shown_at = ?
                WHERE id = ?
            """, (new_remaining, int(datetime.now().timestamp()), ch["id"]))
            ch["_completed"] = False

        return ch


async def notify_ads_complete(context, ch):
    """ارسال پیام تکمیل سفارش Ads به ادمین"""
    try:
        from config import Config
        await context.bot.send_message(
            Config.ADMIN_ID,
            f"✅ تکمیل سفارش کانال Ads :\n"
            f"\n"
            f"📢 نام کانال : {ch['display_name']}\n"
            f"🔢 مقدار ثبت : {ch.get('_original_remaining', '?')}\n"
            f"📆 تاریخ شروع : {_format_jalali_date(ch['created_at'])}"
        )
    except Exception as e:
        print(f"notify_ads_complete error: {e}")
