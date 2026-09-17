from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    get_user, set_user_state, get_user_state, is_admin
)
from utils.keyboards import inline, main_menu, admin_panel, back_button
from utils.helpers import is_positive_int, jalali_now
from datetime import datetime, timedelta


# ==================== منوی ارسال پیام ====================
async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    set_user_state(user_id, "none")
    
    await update.message.reply_text(
        "📨 نوع ارسال را انتخاب کنید:",
        reply_markup=inline([
            [("📤 ارسال در ربات", "bc_to_bot"), ("📢 ارسال در کانال", "bc_to_channel")],
            [("👤 ارسال به کاربر خاص", "bc_to_user"), ("📌 ارسال در کانال خاص", "bc_to_specific_channel")],
            [("🔙 بازگشت به پنل مدیریت", "bc_back_to_panel")],
        ])
    )


# ==================== بازگشت به پنل مدیریت ====================
async def back_to_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "👑 پنل مدیریت",
        reply_markup=admin_panel()
    )


# ==================== ارسال در ربات ====================
async def bc_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    
    await q.message.edit_text(
        "به چه کسانی می‌خواهید پیام ارسال کنید؟",
        reply_markup=inline([
            [("👥 همه کاربران", "bc_bot_all")],
            [("🟢 کاربران فعال در 3 روز گذشته", "bc_bot_active3")],
            [("🔴 کاربران غیرفعال در 3 روز گذشته", "bc_bot_inactive3")],
            [("🔴 کاربران غیرفعال در 7 روز گذشته", "bc_bot_inactive7")],
            [("🔙 بازگشت به پنل مدیریت", "bc_back_to_panel")],
        ])
    )


async def bc_bot_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    data = q.data
    
    target_map = {
        "bc_bot_all": "all",
        "bc_bot_active3": "active3",
        "bc_bot_inactive3": "inactive3",
        "bc_bot_inactive7": "inactive7",
    }
    
    target = target_map.get(data)
    if not target:
        return
    
    set_user_state(user_id, "bc_text_input", {
        "type": "bot",
        "target": target,
    })
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        user_id,
        "لطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )


# ==================== ارسال در کانال ====================
async def bc_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    set_user_state(user_id, "bc_text_input", {
        "type": "channel_all",
    })
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        user_id,
        "لطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )


# ==================== ارسال به کاربر خاص ====================
async def bc_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    set_user_state(user_id, "bc_user_search")
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        user_id,
        "نام کاربری، یوزرنیم یا شناسه کاربری فرد مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )


# ==================== ارسال در کانال خاص ====================
async def bc_to_specific_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    set_user_state(user_id, "bc_channel_search")
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        user_id,
        "نام کانال، ایدی کانال یا شناسه عددی کانال مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )


# ==================== تأیید ارسال ====================
async def bc_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    state, data = get_user_state(user_id)
    if state != "bc_confirm":
        return
    
    text = data.get("text", "")
    target_type = data.get("type", "")
    target_id = data.get("target_id")
    
    # حذف پیام تأیید
    try:
        await q.message.delete()
    except Exception:
        pass
    
    # ارسال
    sent = 0
    failed = 0
    
    if target_type == "bot":
        # ارسال به کاربران ربات
        target = data.get("target", "all")
        
        with db.conn() as c:
            if target == "all":
                rows = c.execute("SELECT user_id FROM users WHERE banned = 0").fetchall()
            elif target == "active3":
                rows = c.execute("""
                    SELECT user_id FROM users
                    WHERE banned = 0 AND last_daily >= ?
                """, (int(datetime.now().timestamp()) - 3*86400,)).fetchall()
            elif target == "inactive3":
                rows = c.execute("""
                    SELECT user_id FROM users
                    WHERE banned = 0 AND (last_daily < ? OR last_daily = 0)
                """, (int(datetime.now().timestamp()) - 3*86400,)).fetchall()
            elif target == "inactive7":
                rows = c.execute("""
                    SELECT user_id FROM users
                    WHERE banned = 0 AND (last_daily < ? OR last_daily = 0)
                """, (int(datetime.now().timestamp()) - 7*86400,)).fetchall()
            else:
                rows = []
        
        for r in rows:
            try:
                await context.bot.send_message(r["user_id"], text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
    
    elif target_type == "channel_all":
        # ارسال به همه کانال‌هایی که ربات ادمین هست
        # دریافت از دیتابیس — کانال‌هایی که سفارش داشتن
        with db.conn() as c:
            channels = c.execute("""
                SELECT DISTINCT channel FROM orders
                WHERE status IN ('running', 'completed')
            """).fetchall()
        
        for ch in channels:
            try:
                await context.bot.send_message(f"@{ch['channel']}", text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
    
    elif target_type == "specific_channel":
        # ارسال به کانال خاص
        if target_id:
            try:
                await context.bot.send_message(target_id, text, parse_mode="HTML")
                sent += 1
            except Exception as e:
                failed += 1
                await context.bot.send_message(user_id, f"❌ خطا: {e}")
    
    elif target_type == "specific_user":
        # ارسال به کاربر خاص
        if target_id:
            try:
                await context.bot.send_message(target_id, text, parse_mode="HTML")
                sent += 1
            except Exception as e:
                failed += 1
                await context.bot.send_message(user_id, f"❌ خطا: {e}")
    
    set_user_state(user_id, "none")
    
    await context.bot.send_message(
        user_id,
        f"✅ ارسال شد.\n✔️ موفق: {sent}\n❌ ناموفق: {failed}",
        reply_markup=admin_panel()
    )


async def bc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("لغو شد.")
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "👑 پنل مدیریت",
        reply_markup=admin_panel()
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
    
    # === بازگشت ===
    if text == "🔙 بازگشت به پنل مدیریت" or text == "بازگشت به پنل مدیریت":
        set_user_state(user_id, "none")
        await update.message.reply_text(
            "👑 پنل مدیریت",
            reply_markup=admin_panel()
        )
        return True
    
    # === دریافت متن پیام ===
    if state == "bc_text_input":
        set_user_state(user_id, "bc_confirm", {**data, "text": text})
        await update.message.reply_text(
            "آیا از ارسال پیام خود مطمئن هستید؟",
            reply_markup=inline([
                [("✅ بله", "bc_confirm_yes"), ("❌ خیر", "bc_confirm_no")],
            ])
        )
        return True
    
    # === جستجوی کاربر ===
    if state == "bc_user_search":
        query = text.strip()
        # حذف @
        query_clean = query.lstrip("@")
        
        with db.conn() as c:
            # جستجو با آیدی عددی
            if query_clean.isdigit():
                users = c.execute(
                    "SELECT user_id, first_name, username FROM users WHERE user_id = ? LIMIT 10",
                    (int(query_clean),)
                ).fetchall()
            else:
                # جستجو با یوزرنیم یا نام
                users = c.execute("""
                    SELECT user_id, first_name, username FROM users
                    WHERE username LIKE ? OR first_name LIKE ?
                    LIMIT 10
                """, (f"%{query_clean}%", f"%{query}%")).fetchall()
        
        if not users:
            await update.message.reply_text(
                "کاربری با مشخصات ارسالی یافت نشد\n"
                "لطفا دوباره ارسال فرمایید:",
                reply_markup=back_button()
            )
            return True
        
        # نمایش لیست کاربران
        result_text = f"{len(users)} کاربر یافت شد:\n\n"
        rows = []
        for i, u in enumerate(users, 1):
            name = u["first_name"] or "کاربر"
            username = f"@{u['username']}" if u["username"] else "ندارد"
            result_text += (
                f"{i}. نام کاربری : {name}\n"
                f"🆔 یوزرنیم : {username}\n"
                f"🔰 شماره کاربری : {u['user_id']}\n\n"
            )
            rows.append([
                (f"📤 ارسال به {name}", f"bc_user_pick:{u['user_id']}")
            ])
        rows.append([("🔙 بازگشت به پنل مدیریت", "bc_back_to_panel")])
        
        await update.message.reply_text(
            result_text,
            reply_markup=inline(rows)
        )
        return True
    
    # === انتخاب کاربر ===
    if state == "bc_user_search" or True:  # برای callback جداگانه
        pass
    
    # === جستجوی کانال ===
    if state == "bc_channel_search":
        query = text.strip()
        query_clean = query.lstrip("@")
        
        # جستجو در کانال‌های شناخته شده (سفارش‌ها)
        with db.conn() as c:
            if query_clean.isdigit() or query_clean.startswith("-"):
                channels = c.execute("""
                    SELECT DISTINCT channel, channel_id FROM orders
                    WHERE channel_id = ? LIMIT 10
                """, (query_clean,)).fetchall()
            else:
                channels = c.execute("""
                    SELECT DISTINCT channel, channel_id FROM orders
                    WHERE channel LIKE ? LIMIT 10
                """, (f"%{query_clean}%",)).fetchall()
        
        if not channels:
            await update.message.reply_text(
                "کانالی با مشخصات ارسالی یافت نشد\n"
                "لطفا دوباره ارسال فرمایید:",
                reply_markup=back_button()
            )
            return True
        
        # نمایش لیست کانال‌ها
        result_text = f"{len(channels)} کانال یافت شد:\n\n"
        rows = []
        for i, ch in enumerate(channels, 1):
            username = ch["channel"]
            channel_id = ch["channel_id"] or "نامشخص"
            result_text += (
                f"{i}. نام کانال: @{username}\n"
                f"🆔 یوزرنیم : @{username}\n"
                f"🔰 شناسه عددی : {channel_id}\n\n"
            )
            rows.append([
                (f"📤 ارسال به @{username}", f"bc_channel_pick:{channel_id}")
            ])
        rows.append([("🔙 بازگشت به پنل مدیریت", "bc_back_to_panel")])
        
        await update.message.reply_text(
            result_text,
            reply_markup=inline(rows)
        )
        return True
    
    return False


# ==================== انتخاب کاربر/کانال از دکمه ====================
async def bc_user_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    target_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        target = c.execute(
            "SELECT first_name, username FROM users WHERE user_id = ?",
            (target_id,)
        ).fetchone()
    
    name = target["first_name"] if target else "کاربر"
    
    set_user_state(user_id, "bc_text_input", {
        "type": "specific_user",
        "target_id": target_id,
    })
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        user_id,
        f"شما در حال ارسال پیام به {name} هستید\n"
        f"لطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )


async def bc_channel_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    target_id = q.data.split(":")[1]
    
    set_user_state(user_id, "bc_text_input", {
        "type": "specific_channel",
        "target_id": target_id,
    })
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        user_id,
        f"شما در حال ارسال پیام در کانال هستید\n"
        f"لطفا متن پیام خود را وارد فرمایید :",
        reply_markup=back_button()
    )


# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    user_id = q.from_user.id
    
    if not is_admin(user_id):
        return False
    
    # === منوی ارسال ===
    if data == "bc_send_menu":
        await q.answer()
        await q.message.edit_text(
            "📨 نوع ارسال را انتخاب کنید:",
            reply_markup=inline([
                [("📤 ارسال در ربات", "bc_to_bot"), ("📢 ارسال در کانال", "bc_to_channel")],
                [("👤 ارسال به کاربر خاص", "bc_to_user"), ("📌 ارسال در کانال خاص", "bc_to_specific_channel")],
                [("🔙 بازگشت به پنل مدیریت", "bc_back_to_panel")],
            ])
        )
        return True
    
    if data == "bc_back_to_panel":
        await back_to_panel(update, context)
        return True
    
    if data == "bc_to_bot":
        await bc_to_bot(update, context)
        return True
    
    if data in ("bc_bot_all", "bc_bot_active3", "bc_bot_inactive3", "bc_bot_inactive7"):
        await bc_bot_target(update, context)
        return True
    
    if data == "bc_to_channel":
        await bc_to_channel(update, context)
        return True
    
    if data == "bc_to_user":
        await bc_to_user(update, context)
        return True
    
    if data == "bc_to_specific_channel":
        await bc_to_specific_channel(update, context)
        return True
    
    if data == "bc_confirm_yes":
        await bc_confirm(update, context)
        return True
    
    if data == "bc_confirm_no":
        await bc_cancel(update, context)
        return True
    
    if data.startswith("bc_user_pick:"):
        await bc_user_pick(update, context)
        return True
    
    if data.startswith("bc_channel_pick:"):
        await bc_channel_pick(update, context)
        return True
    
    return False
