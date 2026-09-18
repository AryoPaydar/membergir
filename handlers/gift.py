from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    get_user, set_user_state, get_user_state,
    add_coins, is_admin, get_setting, update_user
)
from utils.keyboards import (
    main_menu, back_button, admin_panel, inline,
    gift_user_back_keyboard
)
from utils.helpers import is_positive_int, now_ts, jalali_now
import math


# ==================== منوی کاربر ====================
async def gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_user_state(user_id, "gift_code")
    await update.message.reply_text(
        "🎁 کد هدیه خود را ارسال کنید:",
        reply_markup=gift_user_back_keyboard()
    )


async def redeem_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = (update.message.text or "").strip()
    
    with db.conn() as c:
        row = c.execute("""
            SELECT * FROM gift_codes
            WHERE code = ? AND type = 'global' AND is_active = 1
            ORDER BY id DESC LIMIT 1
        """, (code,)).fetchone()
        
        if not row:
            await update.message.reply_text(
                "کاربر گرامی \n"
                "کد ارسالی شما صحیح نمیباشد. لطفا دوباره تلاش کنید",
                reply_markup=gift_user_back_keyboard()
            )
            return
        
        code_id = row["id"]
        amount = row["amount"]
        max_users = row["max_users"]
        used_count = row["used_count"]
        post_success_id = row["post_success_id"]
        
        dup = c.execute(
            "SELECT 1 FROM gift_code_users WHERE code_id = ? AND user_id = ?",
            (code_id, user_id)
        ).fetchone()
        if dup:
            set_user_state(user_id, "none")
            await update.message.reply_text(
                "کاربر گرامی\n"
                "شما قبلا از این کد هدیه خود را دریافت کردید.",
                reply_markup=main_menu(is_admin(user_id))
            )
            return
        
        if used_count >= max_users:
            set_user_state(user_id, "none")
            await update.message.reply_text(
                "کاربر گرامی \n"
                "کد وارد شده شما منقضی شده است.",
                reply_markup=main_menu(is_admin(user_id))
            )
            return
        
        c.execute(
            "INSERT INTO gift_code_users (code_id, user_id) VALUES (?, ?)",
            (code_id, user_id)
        )
        c.execute(
            "UPDATE gift_codes SET used_count = used_count + 1 WHERE id = ?",
            (code_id,)
        )
        new_used = used_count + 1
    
    add_coins(user_id, amount, "gift", f"کد هدیه: {code}")
    
    set_user_state(user_id, "none")
    await update.message.reply_text(
        f"تبریک\n"
        f"شما {amount:,} سکه هدیه دریافت کردید.",
        reply_markup=main_menu(is_admin(user_id))
    )
    
    await _send_or_edit_success_post(context, code_id, code, amount, new_used, max_users, post_success_id)


# ==================== ارسال/ادیت پست موفقیت ====================
async def _send_or_edit_success_post(context, code_id, code, amount, used, max_users, post_success_id):
    """ارسال پست موفقیت جدید یا ادیت پست قبلی"""
    if not Config.ADS_CHANNEL:
        return
    
    with db.conn() as c:
        users = c.execute("""
            SELECT u.user_id, u.first_name, u.username
            FROM gift_code_users gcu
            JOIN users u ON u.user_id = gcu.user_id
            WHERE gcu.code_id = ?
            ORDER BY gcu.used_at ASC
        """, (code_id,)).fetchall()
    
    hour, _ = jalali_now()
    today, _ = jalali_now()
    
    users_text = "👤 توسط :\n\n"
    for u in users:
        users_text += (
            f"👤Name: {u['first_name'] or 'کاربر'}\n"
            f"🌐UserID: {u['user_id']}\n\n"
        )
    
    text = (
        f"🎟 کد {code} با مقدار سکه {amount:,} توسط {used}/{max_users} نفر موفقیت استفاده شد\n"
        f"\n"
        f"⏰ ساعت ↙️\n"
        f"⏰{hour}\n"
        f"📆تاریخ↙️\n"
        f"📆 {today}\n"
        f"\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"{users_text}"
        f"➖➖➖➖➖➖➖➖➖➖➖➖"
    )
    
    try:
        if post_success_id:
            await context.bot.edit_message_text(
                chat_id=f"@{Config.ADS_CHANNEL}",
                message_id=post_success_id,
                text=text
            )
        else:
            msg = await context.bot.send_message(
                f"@{Config.ADS_CHANNEL}",
                text
            )
            with db.conn() as c:
                c.execute(
                    "UPDATE gift_codes SET post_success_id = ? WHERE id = ?",
                    (msg.message_id, code_id)
                )
    except Exception as e:
        print(f"Gift success post error: {e}")


# ==================== منوی ادمین ====================
async def gift_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    await update.message.reply_text(
        "چه کاری میخواهید انجام دهید ؟",
        reply_markup=inline([
            [("📤 ارسال در گروه", "gift_admin_group"), ("👤 ارسال به کاربر", "gift_admin_user")],
            [("📜 کدهای سابق", "gift_admin_history")],
            [("🔙 بازگشت به پنل مدیریت", "gift_admin_back")],
        ])
    )


async def gift_admin_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id, "👑 پنل مدیریت",
        reply_markup=admin_panel()
    )


# ==================== ارسال در گروه ====================
async def gift_admin_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "gift_code_create_code")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "کد مورد نظر خود را ارسال فرمایید :\n\n"
        "کاربران برای دریافت هدیه باید این کد را وارد نمایند",
        reply_markup=back_button()
    )


# ==================== ارسال به کاربر ====================
async def gift_admin_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "gift_search_user")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "نام کاربری، یوزرنیم یا شناسه کاربری فرد مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )


# ==================== کدهای سابق ====================
async def gift_admin_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "نوع هدیه خود را خود را انتخاب کنید :",
        reply_markup=inline([
            [("🎁 هدیه به کاربران", "gift_hist_single"), ("🎁 هدیه همگانی", "gift_hist_global")],
            [("🔙 بازگشت به پنل مدیریت", "gift_admin_back")],
        ])
    )


# ==================== نمایش لیست کدهای سابق ====================
async def _format_gift_list(gifts, page, kind):
    per_page = 5
    total = len(gifts)
    start = page * per_page
    chunk = gifts[start:start+per_page]
    
    if kind == "global":
        txt = f"تعداد هدیه های سابق : {total}\n\n"
        for i, g in enumerate(chunk, start+1):
            txt += f"{i}. کد هدیه {g['code']} مقدار {g['amount']:,}\n"
            txt += f"👥 دریافت‌کنندگان ({g['used_count']}/{g['max_users']}):\n"
            with db.conn() as c:
                users = c.execute("""
                    SELECT u.user_id, u.first_name, u.username
                    FROM gift_code_users gcu
                    JOIN users u ON u.user_id = gcu.user_id
                    WHERE gcu.code_id = ?
                    ORDER BY gcu.used_at ASC
                """, (g["id"],)).fetchall()
            for j, u in enumerate(users, 1):
                username = f"@{u['username']}" if u['username'] else "ندارد"
                txt += (
                    f"{j}.🗣 نام کاربری : {u['first_name'] or 'کاربر'}\n"
                    f"🆔 یوزرنیم : {username}\n"
                    f"🔰 شماره کاربری : {u['user_id']}\n"
                    f"---\n"
                )
            txt += "---------------------------\n"
    else:
        txt = f"تعداد هدیه های سابق : {total}\n\n"
        for i, g in enumerate(chunk, start+1):
            target_user = get_user(g["target_user_id"])
            name = target_user["first_name"] if target_user else "کاربر"
            username = f"@{target_user['username']}" if target_user and target_user.get("username") else "ندارد"
            txt += (
                f"{i}. مقدار {g['amount']:,} سکه\n"
                f"👤 دریافت‌کننده : {name}\n"
                f"🆔 یوزرنیم : {username}\n"
                f"🔰 شماره کاربری : {g['target_user_id']}\n"
                f"---------------------------\n"
            )
    
    return txt


async def gift_hist_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    page = 0
    if ":" in q.data:
        page = int(q.data.split(":")[1])
    
    with db.conn() as c:
        gifts = c.execute("""
            SELECT * FROM gift_codes
            WHERE type = 'global' AND is_active = 1
            ORDER BY id DESC
        """).fetchall()
    
    if not gifts:
        await q.message.edit_text(
            "هیچ هدیه‌ای وجود ندارد.",
            reply_markup=inline([[("🔙 بازگشت", "gift_admin_history")]])
        )
        return
    
    txt = await _format_gift_list(gifts, page, "global")
    
    total_pages = math.ceil(len(gifts) / 5)
    rows = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"gift_hist_global:{page-1}"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"gift_hist_global:{page+1}"))
        rows.append(nav)
    for g in gifts[page*5:page*5+5]:
        rows.append([(f"🗑 حذف کد {g['code']}", f"gift_del_global:{g['id']}")])
    rows.append([("🔙 بازگشت به پنل مدیریت", "gift_admin_back")])
    
    try:
        await q.message.edit_text(txt, reply_markup=inline(rows))
    except Exception:
        pass


async def gift_hist_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    page = 0
    if ":" in q.data:
        page = int(q.data.split(":")[1])
    
    with db.conn() as c:
        gifts = c.execute("""
            SELECT * FROM gift_codes
            WHERE type = 'single' AND is_active = 1
            ORDER BY id DESC
        """).fetchall()
    
    if not gifts:
        await q.message.edit_text(
            "هیچ هدیه‌ای وجود ندارد.",
            reply_markup=inline([[("🔙 بازگشت", "gift_admin_history")]])
        )
        return
    
    txt = await _format_gift_list(gifts, page, "single")
    
    total_pages = math.ceil(len(gifts) / 5)
    rows = []
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(("⬅️ قبلی", f"gift_hist_single:{page-1}"))
        if page < total_pages - 1:
            nav.append(("بعدی ➡️", f"gift_hist_single:{page+1}"))
        rows.append(nav)
    for g in gifts[page*5:page*5+5]:
        rows.append([(f"🗑 حذف هدیه به {g['target_user_id']}", f"gift_del_single:{g['id']}")])
    rows.append([("🔙 بازگشت به پنل مدیریت", "gift_admin_back")])
    
    try:
        await q.message.edit_text(txt, reply_markup=inline(rows))
    except Exception:
        pass


async def gift_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    parts = data.split(":")
    kind = parts[0].split("_")[-1]
    gift_id = int(parts[1])
    
    with db.conn() as c:
        c.execute("UPDATE gift_codes SET is_active = 0 WHERE id = ?", (gift_id,))
    
    await q.answer("✅ حذف شد.", show_alert=True)
    if kind == "global":
        q.data = "gift_hist_global:0"
        await gift_hist_global(update, context)
    else:
        q.data = "gift_hist_single:0"
        await gift_hist_single(update, context)


# ==================== جستجوی کاربر ====================
async def handle_gift_user_search(update, context, text):
    query_clean = text.strip().lstrip("@")
    
    if not query_clean:
        await update.message.reply_text(
            "کاربری با مشخصات ارسالی مطابقت نداشت. لطفا دوباره تلاش کنید",
            reply_markup=back_button()
        )
        return
    
    with db.conn() as c:
        if query_clean.isdigit():
            users = c.execute(
                "SELECT user_id, first_name, username FROM users WHERE user_id = ?",
                (int(query_clean),)
            ).fetchall()
        else:
            users = c.execute(
                "SELECT user_id, first_name, username FROM users WHERE username LIKE ? OR first_name LIKE ?",
                (f"%{query_clean}%", f"%{query_clean}%")
            ).fetchall()
    
    if not users:
        await update.message.reply_text(
            "کاربری با مشخصات ارسالی مطابقت نداشت. لطفا دوباره تلاش کنید",
            reply_markup=back_button()
        )
        return
    
    txt = f"{len(users)} کاربر یافت شد:\n\n"
    rows = []
    for i, u in enumerate(users[:10], 1):
        name = u["first_name"] or "کاربر"
        username = f"@{u['username']}" if u["username"] else "ندارد"
        txt += (
            f"{i}. نام کاربری : {name}\n"
            f"🆔 یوزرنیم : {username}\n"
            f"🔰 شماره کاربری : {u['user_id']}\n\n"
        )
        rows.append([(f"📤 ارسال به {name}", f"gift_user_pick:{u['user_id']}")])
    rows.append([("🔙 بازگشت به پنل مدیریت", "gift_admin_back")])
    
    await update.message.reply_text(txt, reply_markup=inline(rows))


# ==================== انتخاب کاربر ====================
async def gift_user_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    try:
        uid = int(q.data.split(":")[1])
    except (ValueError, IndexError):
        return
    
    user = get_user(uid)
    name = user["first_name"] if user else "کاربر"
    
    set_user_state(q.from_user.id, "gift_user_amount", {"target_id": uid})
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    await context.bot.send_message(
        q.from_user.id,
        f"شما در حال ارسال هدیه به {name} هستید\nلطفا مقدار هدیه خود را وارد فرمایید :",
        reply_markup=back_button()
    )


# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if not state or state == "none":
        return False
    
    # ===== کاربر =====
    if state == "gift_code":
        if text == "🔙 انصراف":
            set_user_state(user_id, "none")
            await update.message.reply_text(
                "🏠 منوی اصلی",
                reply_markup=main_menu(is_admin(user_id))
            )
            return True
        await redeem_gift(update, context)
        return True
    
    # ===== ادمین =====
    if not is_admin(user_id):
        return False
    
    if state == "gift_code_create_code":
        set_user_state(user_id, "gift_code_create_amount", {"code": text})
        await update.message.reply_text(
            "تعداد سکه هدیه چقدر باشه ؟",
            reply_markup=back_button()
        )
        return True
    
    if state == "gift_code_create_amount":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_user_state(user_id, "gift_code_create_max", {**data, "amount": int(text)})
        await update.message.reply_text(
            "تعداد افرادی که میتوانند هدیه را دریافت نمایند وارد کنید :",
            reply_markup=back_button()
        )
        return True
    
    if state == "gift_code_create_max":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        code = data.get("code")
        amount = data.get("amount")
        max_users = int(text)
        set_user_state(user_id, "gift_code_confirm", {
            "code": code, "amount": amount, "max_users": max_users
        })
        await update.message.reply_text(
            f"آیا از تصمیم خود مطمئن هستید ؟\n\n"
            f"🎟 کد : {code}\n"
            f"💰 سکه : {amount:,}\n"
            f"👤 تعداد نفرات : {max_users}",
            reply_markup=inline([
                [("✅ بله", "gift_create_yes"), ("❌ خیر", "gift_create_no")],
            ])
        )
        return True
    
    if state == "gift_search_user":
        await handle_gift_user_search(update, context, text)
        return True
    
    if state == "gift_user_amount":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        target_id = data.get("target_id")
        user = get_user(target_id)
        name = user["first_name"] if user else "کاربر"
        set_user_state(user_id, "gift_user_confirm", {
            "target_id": target_id, "amount": int(text)
        })
        await update.message.reply_text(
            f"آیا از ارسال {int(text):,} هدیه به {name} مطمئن هستید ؟",
            reply_markup=inline([
                [("✅ بله", "gift_user_yes"), ("❌ خیر", "gift_admin_back")],
            ])
        )
        return True
    
    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    user_id = q.from_user.id
    
    if not is_admin(user_id):
        return False
    
    if data == "gift_admin_group":
        await gift_admin_group(update, context)
        return True
    if data == "gift_admin_user":
        await gift_admin_user(update, context)
        return True
    if data == "gift_admin_history":
        await gift_admin_history(update, context)
        return True
    if data == "gift_admin_back":
        await gift_admin_back(update, context)
        return True
    if data == "gift_hist_global" or data.startswith("gift_hist_global:"):
        await gift_hist_global(update, context)
        return True
    if data == "gift_hist_single" or data.startswith("gift_hist_single:"):
        await gift_hist_single(update, context)
        return True
    if data.startswith("gift_del_global:") or data.startswith("gift_del_single:"):
        await gift_del_confirm(update, context)
        return True
    if data.startswith("gift_user_pick:"):
        await gift_user_pick(update, context)
        return True
    
    if data == "gift_create_yes":
        await q.answer()
        state, sdata = get_user_state(user_id)
        if state != "gift_code_confirm":
            return True
        
        code = sdata.get("code")
        amount = sdata.get("amount")
        max_users = sdata.get("max_users")
        
        with db.conn() as c:
            cur = c.execute("""
                INSERT INTO gift_codes (code, amount, max_users, type, created_by)
                VALUES (?, ?, ?, 'global', ?)
            """, (code, amount, max_users, user_id))
            code_id = cur.lastrowid
        
        hour, _ = jalali_now()
        today, _ = jalali_now()
        
        post_text = (
            f"🎁 کد هدیه جدید ساخته شد👌\n"
            f"\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"🎟 کد : {code}\n"
            f"\n"
            f"🤩 تعداد سکه : {amount:,} 💰\n"
            f"\n"
            f"🥰 تعداد نفرات : {max_users} 👤\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"هرکی زود کد بالا رو داخل ربات بخش کد هدیه بزنه برندست🌀😍\n"
            f"\n"
            f"⏰زمان ◀️ {hour}\n"
            f"\n"
            f"📆تاریخ ◀️ {today}"
        )
        
        bot_username = (await context.bot.get_me()).username
        
        try:
            msg = await context.bot.send_message(
                f"@{Config.ADS_CHANNEL}",
                post_text,
                reply_markup=inline([
                    [("🎁 ورود به ربات", f"https://t.me/{bot_username}")],
                ])
            )
            with db.conn() as c:
                c.execute("UPDATE gift_codes SET post_id = ? WHERE id = ?", (msg.message_id, code_id))
        except Exception as e:
            await context.bot.send_message(user_id, f"❌ خطا در ارسال به گروه: {e}")
        
        set_user_state(user_id, "none")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            user_id,
            "✅ کد هدیه با موفقیت ساخته و به گروه ارسال شد.",
            reply_markup=admin_panel()
        )
        return True
    
    if data == "gift_create_no":
        await q.answer("لغو شد.")
        set_user_state(user_id, "none")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(user_id, "👑 پنل مدیریت", reply_markup=admin_panel())
        return True
    
    if data == "gift_user_yes":
        await q.answer()
        state, sdata = get_user_state(user_id)
        if state != "gift_user_confirm":
            return True
        
        target_id = sdata.get("target_id")
        amount = sdata.get("amount")
        
        with db.conn() as c:
            c.execute("""
                INSERT INTO gift_codes (code, amount, max_users, used_count, type, target_user_id, created_by)
                VALUES (?, ?, 1, 1, 'single', ?, ?)
            """, ("", amount, target_id, user_id))
        
        add_coins(target_id, amount, "admin_gift", "هدیه از طرف مدیریت")
        
        try:
            await context.bot.send_message(
                target_id,
                f"🎉 تبریک\n\n"
                f"شما {amount:,} سکه از طرف مدیریت دریافت کردید."
            )
        except Exception:
            pass
        
        set_user_state(user_id, "none")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            user_id,
            f"✅ هدیه {amount:,} سکه به کاربر ارسال شد.",
            reply_markup=admin_panel()
        )
        return True
    
    return False
