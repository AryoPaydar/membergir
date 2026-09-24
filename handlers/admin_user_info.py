from telegram import Update
from telegram.ext import ContextTypes
from database import db
from config import Config
from bot_manager import (
    is_admin, set_user_state, get_user_state, get_user,
    update_user, add_warning, ban_user, unban_user,
    add_coins, remove_coins
)
from utils.keyboards import (
    inline, back_button, admin_panel, main_menu, admin_back_keyboard
)
from utils.helpers import is_positive_int, now_ts, jalali_now
from datetime import datetime
import jdatetime
import math


# ==================== منوی مدیریت کاربران ====================
async def users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    set_user_state(update.effective_user.id, "none")

    with db.conn() as c:
        total = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        banned = c.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
        warned = c.execute("SELECT COUNT(*) c FROM users WHERE warnings > 0").fetchone()["c"]

        active_users = c.execute("""
            SELECT COUNT(DISTINCT admin_id) c FROM orders WHERE status = 'running'
        """).fetchone()["c"]

        inactive_users = total - active_users

    text = (
        f"⚜️ مجموع کاربران : {total:,}\n"
        f"🚫 کاربران بن شده : {banned:,}\n"
        f"⚠️ کاربران دارای اخطار : {warned:,}\n"
        f"⛓️ کاربران داری سفارش فعال : {active_users:,}\n"
        f"⛓️ کاربران بدون سفارش فعال : {inactive_users:,}"
    )

    keyboard = inline([
        [("👥 نمایش همه کاربران", "au_all:0"), ("🔍 جستجوی کاربران", "au_search")],
        [("🚫 کاربران بن شده", "au_banned:0"), ("⚠️ کاربران دارای اخطار", "au_warned:0")],
        [("⛓️ کاربران بدون سفارش", "au_no_order:0"), ("⛓️ کاربران دارای سفارش", "au_has_order:0")],
        [("🔙 بازگشت به پنل مدیریت", "au_back")],
    ])

    await update.message.reply_text(text, reply_markup=keyboard)


async def au_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


# ==================== نمایش لیست کاربران ====================
async def _show_users_list(update, context, users, page, title, filter_type):
    q = update.callback_query
    per_page = 10

    total = len(users)
    total_pages = math.ceil(total / per_page) if total else 0

    if not users:
        await q.message.edit_text(
            f"{title}\n\n❌ هیچ کاربری یافت نشد.",
            reply_markup=inline([[("🔙 بازگشت", "au_menu")]])
        )
        return

    start = page * per_page
    chunk = users[start:start+per_page]

    text = f"{title}\n👥 تعداد : {total} کاربر\n\n"
    rows = []

    for i, u in enumerate(chunk, start+1):
        name = (u["first_name"] or "کاربر")[:20]
        rows.append([
            (f"👤 {name} | {u['user_id']}", f"au_show:{u['user_id']}")
        ])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"au_{filter_type}:{page-1}"))
        nav.append((f"{page+1}/{total_pages}", "noop"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"au_{filter_type}:{page+1}"))
        rows.append(nav)

    rows.append([("🔙 بازگشت به منوی مدیریت کاربران", "au_menu")])

    try:
        await q.message.edit_text(text, reply_markup=inline(rows))
    except Exception:
        pass


# ==================== فیلترها ====================
async def _handle_filter(update, context, filter_type, page):
    q = update.callback_query
    await q.answer()

    with db.conn() as c:
        if filter_type == "all":
            users = c.execute("SELECT * FROM users ORDER BY join_date DESC").fetchall()
            title = "👥 نمایش همه کاربران :"
        elif filter_type == "banned":
            users = c.execute("SELECT * FROM users WHERE banned = 1 ORDER BY join_date DESC").fetchall()
            title = "🚫 کاربران بن شده :"
        elif filter_type == "warned":
            users = c.execute("SELECT * FROM users WHERE warnings > 0 ORDER BY warnings DESC").fetchall()
            title = "⚠️ کاربران دارای اخطار :"
        elif filter_type == "no_order":
            users = c.execute("""
                SELECT * FROM users
                WHERE user_id NOT IN (
                    SELECT DISTINCT admin_id FROM orders WHERE status = 'running'
                )
                ORDER BY join_date DESC
            """).fetchall()
            title = "⛓️ کاربران بدون سفارش فعال :"
        elif filter_type == "has_order":
            users = c.execute("""
                SELECT DISTINCT u.* FROM users u
                INNER JOIN orders o ON o.admin_id = u.user_id
                WHERE o.status = 'running'
                ORDER BY u.join_date DESC
            """).fetchall()
            title = "⛓️ کاربران دارای سفارش فعال :"
        else:
            return

    users = [dict(u) for u in users]
    await _show_users_list(update, context, users, page, title, filter_type)


# ==================== منوی مدیریت کاربر خاص ====================
async def au_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    target_id = int(q.data.split(":")[1])
    user = get_user(target_id)

    if not user:
        await q.message.edit_text(
            "❌ کاربر یافت نشد.",
            reply_markup=inline([[("🔙 بازگشت", "au_menu")]])
        )
        return

    text = await _build_user_info_text(target_id)

    keyboard = inline([
        [("👥 مشاهده زیرمجموعه ها", f"au_subs:{target_id}"),
         ("🎯 ارتقای پنل کاربر", f"au_upgrade:{target_id}")],
        [("🎁 ارسال هدیه", f"au_gift:{target_id}"),
         ("⚠️ اخطارات", f"au_warns:{target_id}")],
        [("🚫 بن/آن بن کاربر", f"au_ban:{target_id}"),
         ("💳 انتقالات الماس", f"au_transfers:{target_id}")],
        [("📨 ارسال پیام", f"au_msg:{target_id}")],
        [("🔙 بازگشت به منوی مدیریت کاربران", "au_menu")],
    ])

    try:
        await q.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        await q.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _build_user_info_text(user_id):
    user = get_user(user_id)
    if not user:
        return "❌ کاربر یافت نشد."

    try:
        dt = datetime.strptime(str(user["join_date"])[:19], "%Y-%m-%d %H:%M:%S")
        join_date_jalali = jdatetime.date.fromgregorian(date=dt.date()).strftime("%Y/%m/%d")
    except Exception:
        join_date_jalali = str(user.get("join_date", ""))[:10]

    panel = user.get("panel", "عادی")
    is_verified = bool(user.get("phone"))
    verify_status = "تایید شده ✅" if is_verified else "تایید نشده ❌"

    warnings = user.get("warnings", 0)
    max_warn = Config.MAX_WARNINGS

    today, _ = jalali_now()
    today_earned = user.get("today_earned", 0) if user.get("today_date") == today else 0

    total_earned = user.get("total_earned", 0)
    total_spent = user.get("total_spent", 0)

    with db.conn() as c:
        gift_row = c.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE to_id = ? AND type = 'admin_gift'
        """, (user_id,)).fetchone()
        admin_gift = gift_row["total"] if gift_row else 0

        ref_total = c.execute(
            "SELECT COUNT(*) c FROM users WHERE referrer_id = ?", (user_id,)
        ).fetchone()["c"]

        today_jalali = today
        ref_today = 0
        refs = c.execute(
            "SELECT join_date FROM users WHERE referrer_id = ?", (user_id,)
        ).fetchall()
        for r in refs:
            try:
                dt2 = datetime.strptime(str(r["join_date"])[:19], "%Y-%m-%d %H:%M:%S")
                jd = jdatetime.date.fromgregorian(date=dt2.date()).strftime("%Y/%m/%d")
                if jd == today_jalali:
                    ref_today += 1
            except Exception:
                pass

        ref_verified = c.execute("""
            SELECT COUNT(*) c FROM users
            WHERE referrer_id = ? AND ads_joined >= 3
        """, (user_id,)).fetchone()["c"]

        commission_row = c.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE to_id = ? AND type IN ('referral', 'referral_commission')
        """, (user_id,)).fetchone()
        inv_commission = commission_row["total"] if commission_row else 0

    hourly_earned = user.get("hourly_earned", 0)
    last_hourly = user.get("last_hourly", 0)
    now = now_ts()
    cooldown = Config.HOURLY_GIFT_COOLDOWN
    next_hourly = last_hourly + cooldown
    if now < next_hourly:
        remaining = next_hourly - now
        minutes = remaining // 60
        seconds = remaining % 60
        time_left = f"{minutes} دقیقه و {seconds} ثانیه"
    else:
        time_left = "آماده دریافت ✅"

    coins = user.get("coins", 0)
    name = user.get("first_name") or "کاربر"
    username = f"@{user['username']}" if user.get("username") else "ندارد"

    text = (
        f"🔰 نام کاربری : <b>{name}</b>\n"
        f"🆔 یوزرنیم : {username}\n"
        f"🫆 شماره کاربری : <code>{user_id}</code>\n"
        f"📆 تاریخ عضویت : {join_date_jalali}\n"
        f"🏵 نوع پنل : {panel}\n"
        f"💎 حساب کاربری : {verify_status}\n"
        f"⚠️ اخطار : {warnings} از {max_warn}\n"
        f"\n"
        f"📊 مجموع موجودی کسب شده : {total_earned:,}\n"
        f"📈 موجودی کسب شده در امروز : {today_earned:,}\n"
        f"📉 مجموع موجودی مصرفی : {total_spent:,}\n"
        f"🎁 هدیه مدیریت : {admin_gift:,}\n"
        f"🎊 هدیه ساعتی : {hourly_earned:,}\n"
        f"⏳ زمان باقی مانده هدیه ساعتی : {time_left}\n"
        f"\n"
        f"💳 انتقالات\n"
        f"📥 دریافتی : {user.get('received_coins', 0):,}\n"
        f"📤 واریزی : {user.get('sent_coins', 0):,}\n"
        f"\n"
        f"👥 زیر مجموعه ها\n"
        f"⚜️ مجموع : {ref_total:,}\n"
        f"🔆 امروز : {ref_today:,}\n"
        f"💯 زیرمجموعه تایید شده : {ref_verified:,}\n"
        f"💳 پورسانت دریافتی : {inv_commission:,}\n"
        f"\n"
        f"💰 موجودی : <b>{coins:,}</b>"
    )

    return text


# ==================== دکمه‌های مدیریت کاربر ====================
async def au_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[1])

    with db.conn() as c:
        subs = c.execute("""
            SELECT user_id, first_name, username FROM users
            WHERE referrer_id = ?
            ORDER BY join_date DESC
        """, (target_id,)).fetchall()

    if not subs:
        await q.message.reply_text(
            "❌ این کاربر زیرمجموعه‌ای ندارد.",
            reply_markup=inline([[("🔙 بازگشت", f"au_show:{target_id}")]])
        )
        return

    text = f"👥 زیرمجموعه‌های کاربر {target_id} :\n\n"
    for i, s in enumerate(subs, 1):
        name = s["first_name"] or "کاربر"
        username = f"@{s['username']}" if s["username"] else "ندارد"
        text += (
            f"{i}. 🔰 {name}\n"
            f"🆔 {username}\n"
            f"🫆 <code>{s['user_id']}</code>\n\n"
        )

    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", f"au_show:{target_id}")]])
    )


async def au_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[1])

    user = get_user(target_id)
    if not user:
        await q.message.reply_text("❌ کاربر یافت نشد.")
        return

    current_panel = user.get("panel", "عادی")

    await q.message.reply_text(
        f"🎯 ارتقای پنل کاربر {target_id}\n\n"
        f"پنل فعلی : {current_panel}\n\n"
        f"پنل جدید را انتخاب کنید:",
        reply_markup=inline([
            [("📍 عادی", f"au_set_panel:{target_id}:عادی"),
             ("💢 حرفه ای", f"au_set_panel:{target_id}:حرفه ای")],
            [("🌀 ویژه", f"au_set_panel:{target_id}:ویژه")],
            [("🔙 بازگشت", f"au_show:{target_id}")],
        ])
    )


async def au_set_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("✅ پنل تغییر یافت.", show_alert=True)

    parts = q.data.split(":")
    target_id = int(parts[1])
    new_panel = parts[2]

    user = get_user(target_id)
    if not user:
        return

    update_user(target_id, panel=new_panel)

    try:
        await context.bot.send_message(
            target_id,
            f"🎉 پنل شما توسط مدیریت به <b>{new_panel}</b> تغییر یافت.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    q.data = f"au_show:{target_id}"
    await au_show(update, context)


async def au_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[1])

    set_user_state(q.from_user.id, "au_gift_input", {"target_id": target_id})

    await q.message.reply_text(
        f"🎁 ارسال هدیه به کاربر {target_id}\n\n"
        f"مقدار سکه را وارد کنید:",
        reply_markup=back_button()
    )


async def au_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[1])

    user = get_user(target_id)
    if not user:
        await q.message.reply_text("❌ کاربر یافت نشد.")
        return

    warnings = user.get("warnings", 0)

    await q.message.reply_text(
        f"⚠️ اخطارات کاربر {target_id}\n\n"
        f"تعداد اخطار فعلی : {warnings} از {Config.MAX_WARNINGS}",
        reply_markup=inline([
            [("➕ افزودن اخطار", f"au_warn_add:{target_id}")],
            [("➖ صفر کردن اخطارات", f"au_warn_reset:{target_id}")],
            [("🔙 بازگشت", f"au_show:{target_id}")],
        ])
    )


async def au_warn_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    target_id = int(q.data.split(":")[1])

    new_count = add_warning(target_id)
    await q.answer(f"✅ اخطار ثبت شد. تعداد اخطار: {new_count}", show_alert=True)

    try:
        await context.bot.send_message(
            target_id,
            f"⚠️ شما یک اخطار دریافت کردید.\nتعداد اخطار: {new_count} از {Config.MAX_WARNINGS}"
        )
    except Exception:
        pass

    q.data = f"au_warns:{target_id}"
    await au_warns(update, context)


async def au_warn_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    target_id = int(q.data.split(":")[1])

    update_user(target_id, warnings=0)
    await q.answer("✅ اخطارات صفر شد.", show_alert=True)

    q.data = f"au_warns:{target_id}"
    await au_warns(update, context)


async def au_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    target_id = int(q.data.split(":")[1])

    user = get_user(target_id)
    if not user:
        await q.message.reply_text("❌ کاربر یافت نشد.")
        return

    if user.get("banned"):
        unban_user(target_id)
        await q.answer("✅ کاربر آن بن شد.", show_alert=True)
        try:
            await context.bot.send_message(target_id, "✅ شما از ربات آن بن شدید.")
        except Exception:
            pass
    else:
        ban_user(target_id)
        await q.answer("✅ کاربر بن شد.", show_alert=True)
        try:
            await context.bot.send_message(target_id, "⛔️ شما از ربات بن شدید.")
        except Exception:
            pass

    q.data = f"au_show:{target_id}"
    await au_show(update, context)


async def au_transfers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[1])

    with db.conn() as c:
        rows = c.execute("""
            SELECT * FROM transactions
            WHERE (from_id = ? OR to_id = ?) AND type = 'transfer'
            ORDER BY id DESC LIMIT 20
        """, (target_id, target_id)).fetchall()

    if not rows:
        await q.message.reply_text(
            "❌ هیچ انتقالی ثبت نشده.",
            reply_markup=inline([[("🔙 بازگشت", f"au_show:{target_id}")]])
        )
        return

    text = f"💳 انتقالات کاربر {target_id} :\n\n"
    for r in rows:
        sign = "+" if r["to_id"] == target_id else "-"
        other = r["from_id"] if r["to_id"] == target_id else r["to_id"]
        text += (
            f"{sign}{r['amount']:,} | با کاربر {other}\n"
            f"📆 {r['created_at']}\n"
            f"————————————\n"
        )

    await q.message.reply_text(
        text,
        reply_markup=inline([[("🔙 بازگشت", f"au_show:{target_id}")]])
    )


async def au_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[1])

    set_user_state(q.from_user.id, "au_msg_input", {"target_id": target_id})

    await q.message.reply_text(
        f"📨 ارسال پیام به کاربر {target_id}\n\n"
        f"متن پیام را وارد کنید:",
        reply_markup=back_button()
    )


async def au_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    set_user_state(q.from_user.id, "au_search_input")

    await q.message.reply_text(
        "🔍 جستجوی کاربران\n\n"
        "نام کاربری، یوزرنیم یا شناسه کاربری فرد مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
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

    # دکمه بازگشت
    if text == "🔙 بازگشت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True

    # ===== جستجوی کاربر =====
    if state == "au_search_input":
        query_clean = text.strip().lstrip("@")

        if not query_clean:
            await update.message.reply_text(
                "❌ نامعتبر. دوباره تلاش کنید.",
                reply_markup=back_button()
            )
            return True

        with db.conn() as c:
            if query_clean.isdigit():
                users = c.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (int(query_clean),)
                ).fetchall()
            else:
                users = c.execute(
                    "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ?",
                    (f"%{query_clean}%", f"%{query_clean}%")
                ).fetchall()

        users = [dict(u) for u in users]

        if not users:
            await update.message.reply_text(
                "❌ کاربری با این مشخصات یافت نشد. لطفا دوباره تلاش کنید.",
                reply_markup=back_button()
            )
            return True

        text_out = f"🔍 نتایج جستجو : {len(users)} کاربر\n\n"
        rows = []
        for i, u in enumerate(users[:10], 1):
            name = (u["first_name"] or "کاربر")[:20]
            rows.append([
                (f"👤 {name} | {u['user_id']}", f"au_show:{u['user_id']}")
            ])
        rows.append([("🔙 بازگشت به منوی مدیریت کاربران", "au_menu")])

        set_user_state(user_id, "none")
        await update.message.reply_text(text_out, reply_markup=inline(rows))
        return True

    # ===== ارسال هدیه =====
    if state == "au_gift_input":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True

        target_id = data.get("target_id")
        amount = int(text)

        if amount <= 0:
            await update.message.reply_text("❌ مقدار باید مثبت باشد.")
            return True

        add_coins(target_id, amount, "admin_gift", "هدیه از طرف مدیریت")

        with db.conn() as c:
            c.execute(
                "UPDATE users SET send_coin_admin = send_coin_admin + ? WHERE user_id = ?",
                (amount, target_id)
            )

        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"✅ {amount:,} سکه به کاربر {target_id} ارسال شد.",
            reply_markup=admin_panel()
        )

        try:
            await context.bot.send_message(
                target_id,
                f"🎉 تبریک\n\nشما {amount:,} سکه از طرف مدیریت دریافت کردید."
            )
        except Exception:
            pass
        return True

    # ===== ارسال پیام به کاربر =====
    if state == "au_msg_input":
        target_id = data.get("target_id")

        try:
            await context.bot.send_message(
                target_id,
                f"📨 <b>پیام از مدیریت:</b>\n\n{text}",
                parse_mode="HTML"
            )
            await update.message.reply_text(
                f"✅ پیام به کاربر {target_id} ارسال شد.",
                reply_markup=admin_panel()
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ خطا در ارسال: {e}",
                reply_markup=admin_panel()
            )

        set_user_state(user_id, "none")
        return True

    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False

    # 🔮 هندل جستجوگر
    if data.startswith("srch_"):
        return await handle_srch_callback(update, context)

    # منوی مدیریت کاربران
    if data == "au_menu":
        await q.answer()
        await _show_users_menu_callback(update, context)
        return True

    if data == "au_back":
        await au_back(update, context)
        return True

    if data == "au_search":
        await au_search(update, context)
        return True

    if data == "noop":
        await q.answer()
        return True

    # فیلترها
    if data.startswith("au_all:") or data == "au_all":
        page = int(data.split(":")[1]) if ":" in data else 0
        await _handle_filter(update, context, "all", page)
        return True
    if data.startswith("au_banned:") or data == "au_banned":
        page = int(data.split(":")[1]) if ":" in data else 0
        await _handle_filter(update, context, "banned", page)
        return True
    if data.startswith("au_warned:") or data == "au_warned":
        page = int(data.split(":")[1]) if ":" in data else 0
        await _handle_filter(update, context, "warned", page)
        return True
    if data.startswith("au_no_order:") or data == "au_no_order":
        page = int(data.split(":")[1]) if ":" in data else 0
        await _handle_filter(update, context, "no_order", page)
        return True
    if data.startswith("au_has_order:") or data == "au_has_order":
        page = int(data.split(":")[1]) if ":" in data else 0
        await _handle_filter(update, context, "has_order", page)
        return True

    # مدیریت کاربر
    if data.startswith("au_show:"):
        await au_show(update, context)
        return True
    if data.startswith("au_subs:"):
        await au_subs(update, context)
        return True
    if data.startswith("au_upgrade:"):
        await au_upgrade(update, context)
        return True
    if data.startswith("au_set_panel:"):
        await au_set_panel(update, context)
        return True
    if data.startswith("au_gift:"):
        await au_gift(update, context)
        return True
    if data.startswith("au_warns:"):
        await au_warns(update, context)
        return True
    if data.startswith("au_warn_add:"):
        await au_warn_add(update, context)
        return True
    if data.startswith("au_warn_reset:"):
        await au_warn_reset(update, context)
        return True
    if data.startswith("au_ban:"):
        await au_ban(update, context)
        return True
    if data.startswith("au_transfers:"):
        await au_transfers(update, context)
        return True
    if data.startswith("au_msg:"):
        await au_msg(update, context)
        return True

    return False


async def _show_users_menu_callback(update, context):
    q = update.callback_query
    user_id = q.from_user.id

    if not is_admin(user_id):
        return

    set_user_state(user_id, "none")

    with db.conn() as c:
        total = c.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        banned = c.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
        warned = c.execute("SELECT COUNT(*) c FROM users WHERE warnings > 0").fetchone()["c"]
        active_users = c.execute("""
            SELECT COUNT(DISTINCT admin_id) c FROM orders WHERE status = 'running'
        """).fetchone()["c"]
        inactive_users = total - active_users

    text = (
        f"⚜️ مجموع کاربران : {total:,}\n"
        f"🚫 کاربران بن شده : {banned:,}\n"
        f"⚠️ کاربران دارای اخطار : {warned:,}\n"
        f"⛓️ کاربران داری سفارش فعال : {active_users:,}\n"
        f"⛓️ کاربران بدون سفارش فعال : {inactive_users:,}"
    )

    keyboard = inline([
        [("👥 نمایش همه کاربران", "au_all:0"), ("🔍 جستجوی کاربران", "au_search")],
        [("🚫 کاربران بن شده", "au_banned:0"), ("⚠️ کاربران دارای اخطار", "au_warned:0")],
        [("⛓️ کاربران بدون سفارش", "au_no_order:0"), ("⛓️ کاربران دارای سفارش", "au_has_order:0")],
        [("🔙 بازگشت به پنل مدیریت", "au_back")],
    ])

    try:
        await q.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await q.message.reply_text(text, reply_markup=keyboard)


# ================================================================
# ==================== 🔮 جستجوگر (جدید) ====================
# ================================================================

# ==================== منوی اصلی جستجوگر ====================
async def search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی 🔮 جستجوگر — از دکمه ریپلای ادمین"""
    if not is_admin(update.effective_user.id):
        return

    set_user_state(update.effective_user.id, "none")

    await update.message.reply_text(
        "چه چیزی را میخواهید بیابید :",
        reply_markup=inline([
            [("🔍 جستجوگر اعضا", "srch_members"),
             ("📢 جستجوگر کانال", "srch_channels")],
            [("🔙 بازگشت به پنل مدیریت", "srch_back")],
        ])
    )


async def srch_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
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


# ==================== جستجوگر اعضا ====================
async def srch_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    set_user_state(q.from_user.id, "srch_members_input")

    try:
        await q.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        q.from_user.id,
        "آیدی کانال یا گروه مد نظر خود را وارد فرمایید :",
        reply_markup=admin_back_keyboard()
    )


# ==================== جستجوگر کانال ====================
async def srch_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    set_user_state(q.from_user.id, "srch_channels_input")

    try:
        await q.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        q.from_user.id,
        "نام کاربری یا یوزرنیم یا شماره کاربری فرد نظر خود را وارد فرمایید :",
        reply_markup=admin_back_keyboard()
    )


# ==================== توابع جستجو ====================
def _search_users_by_channel(channel: str):
    """پیدا کردن کاربرانی که این کانال رو تبلیغ کردن (بدون تکرار)"""
    channel = channel.lstrip("@").strip()
    with db.conn() as c:
        rows = c.execute("""
            SELECT u.user_id, u.first_name, u.username, MAX(o.id) as last_order
            FROM orders o
            INNER JOIN users u ON u.user_id = o.admin_id
            WHERE o.channel = ?
            GROUP BY u.user_id
            ORDER BY last_order DESC
        """, (channel,)).fetchall()
    return [dict(r) for r in rows]


def _search_channels_by_user(query: str):
    """پیدا کردن کانال‌هایی که یک کاربر تبلیغ کرده (بدون تکرار)"""
    query = query.strip().lstrip("@")
    with db.conn() as c:
        if query.isdigit():
            u = c.execute(
                "SELECT user_id, first_name, username FROM users WHERE user_id = ?",
                (int(query),)
            ).fetchone()
        else:
            u = c.execute(
                "SELECT user_id, first_name, username FROM users WHERE username = ? OR first_name = ? LIMIT 1",
                (query, query)
            ).fetchone()

        if not u:
            return None, []

        rows = c.execute("""
            SELECT DISTINCT channel
            FROM orders
            WHERE admin_id = ?
            ORDER BY channel ASC
        """, (u["user_id"],)).fetchall()

    return dict(u), [r["channel"] for r in rows]


# ==================== نمایش لیست کاربران با صفحه‌بندی ====================
def _format_members_page(users, page):
    per_page = 10
    total = len(users)
    start = page * per_page
    chunk = users[start:start + per_page]

    text = "افرادی که این کانال/گروه را تبلیغ کردند :\n\n"
    for u in chunk:
        name = u["first_name"] or "کاربر"
        username = f"@{u['username']}" if u["username"] else "ندارد"
        text += (
            f"🔰 نام کاربری : {name}\n"
            f"🆔 یوزرنیم : {username}\n"
            f"🫆 شماره کاربری : {u['user_id']}\n"
            f"------------------\n"
        )

    total_pages = math.ceil(total / per_page) if total else 1
    nav_rows = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"srch_members_page:{page-1}"))
        nav.append((f"{page+1}/{total_pages}", "noop"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"srch_members_page:{page+1}"))
        nav_rows.append(nav)

    return text, nav_rows


async def _handle_srch_members_input(update, context, text):
    channel = text.strip().lstrip("@")
    users = _search_users_by_channel(channel)

    if not users:
        await update.message.reply_text(
            "شخصی این کانال یا گروه را تبلیغ نکرده است",
            reply_markup=admin_back_keyboard()
        )
        return

    set_user_state(
        update.effective_user.id,
        "srch_members_result",
        {"channel": channel, "users": users}
    )

    txt, nav_rows = _format_members_page(users, 0)
    rows = nav_rows + [[("🔙 بازگشت به پنل مدیریت", "srch_back")]]

    await update.message.reply_text(txt, reply_markup=inline(rows))


async def _handle_srch_channels_input(update, context, text):
    user, channels = _search_channels_by_user(text)

    if user is None:
        await update.message.reply_text(
            "نام کاربری یا یوزرنیم یا شماره کاربری وارده اشتباه است لطفا دوباره تلاش کنید",
            reply_markup=admin_back_keyboard()
        )
        return

    if not channels:
        await update.message.reply_text(
            "کاربر مورد نظر تبلیغی انجام نداده است",
            reply_markup=admin_back_keyboard()
        )
        return

    name = user["first_name"] or "کاربر"
    text_out = f"تبلغ انجام شده توسط {name} :\n\n"
    for i, ch in enumerate(channels, 1):
        text_out += f"{i}. @{ch.lstrip('@')}\n"

    await update.message.reply_text(
        text_out,
        reply_markup=inline([[("🔙 بازگشت به پنل مدیریت", "srch_back")]])
    )


# ==================== State Handler برای جستجوگر ====================
async def handle_srch_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False

    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()

    if not state or state == "none":
        return False

    if text == "🔙 بازگشت به پنل مدیریت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True

    if state == "srch_members_input":
        await _handle_srch_members_input(update, context, text)
        return True

    if state == "srch_channels_input":
        await _handle_srch_channels_input(update, context, text)
        return True

    return False


# ==================== Callback Handler برای جستجوگر ====================
async def handle_srch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data

    if not is_admin(q.from_user.id):
        return False

    if data == "srch_members":
        await srch_members(update, context)
        return True
    if data == "srch_channels":
        await srch_channels(update, context)
        return True
    if data == "srch_back":
        await srch_back(update, context)
        return True
    if data == "noop":
        await q.answer()
        return True

    if data.startswith("srch_members_page:"):
        await q.answer()
        page = int(data.split(":")[1])
        state, sdata = get_user_state(q.from_user.id)
        if state != "srch_members_result":
            await q.answer("اطلاعات منقضی شده.", show_alert=True)
            return True
        users = sdata.get("users", [])
        if not users:
            return True
        txt, nav_rows = _format_members_page(users, page)
        rows = nav_rows + [[("🔙 بازگشت به پنل مدیریت", "srch_back")]]
        try:
            await q.message.edit_text(txt, reply_markup=inline(rows))
        except Exception:
            pass
        return True

    return False
