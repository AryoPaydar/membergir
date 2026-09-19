from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    is_admin, set_user_state, get_user_state,
    get_user, add_coins, remove_coins, update_user
)
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int, format_number


# ==================== منوی مبادلات سکه ====================
async def coins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    await update.message.reply_text(
        "📌 به بخش مبادلات سکه خوش آمدید 🌹\n\n"
        "✅ گزینه مورد نظر را انتخاب کنید.",
        reply_markup=inline([
            [("📤 کسر سکه", "ac_deduct"), ("📥 اهدای سکه", "ac_gift")],
            [("🔙 بازگشت به پنل مدیریت", "ac_back")],
        ])
    )


async def ac_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


async def ac_deduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "ac_search_user", {"mode": "deduct"})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "نام کاربری، یوزرنیم یا شناسه کاربری فرد مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )


async def ac_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "ac_search_user", {"mode": "gift"})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "نام کاربری، یوزرنیم یا شناسه کاربری فرد مورد نظر را ارسال فرمایید:",
        reply_markup=back_button()
    )


# ==================== جستجوی کاربر ====================
async def handle_search_user(update, context, text, mode):
    query_clean = text.strip().lstrip("@")
    
    if not query_clean:
        await update.message.reply_text(
            "❌ کاربر یافت نشد. لطفا دوباره تلاش کنید",
            reply_markup=back_button()
        )
        return
    
    with db.conn() as c:
        if query_clean.isdigit():
            users = c.execute(
                "SELECT user_id, first_name, username, coins FROM users WHERE user_id = ?",
                (int(query_clean),)
            ).fetchall()
        else:
            users = c.execute(
                "SELECT user_id, first_name, username, coins FROM users WHERE username LIKE ? OR first_name LIKE ?",
                (f"%{query_clean}%", f"%{query_clean}%")
            ).fetchall()
    
    if not users:
        await update.message.reply_text(
            "❌ کاربر یافت نشد. لطفا دوباره تلاش کنید",
            reply_markup=back_button()
        )
        return
    
    # نمایش لیست کاربران
    txt = f"{len(users)} کاربر یافت شد:\n\n"
    rows = []
    for i, u in enumerate(users[:10], 1):
        name = u["first_name"] or "کاربر"
        username = f"@{u['username']}" if u["username"] else "ندارد"
        coins = u["coins"] or 0
        txt += (
            f"{i}. نام کاربری : {name}\n"
            f"🆔 یوزرنیم : {username}\n"
            f"🔰 شماره کاربری : {u['user_id']}\n"
            f"✅ موجودی : {coins:,}\n\n"
        )
        rows.append([
            (f"👤 {name}", f"ac_pick:{mode}:{u['user_id']}")
        ])
    rows.append([("🔙 بازگشت به پنل مدیریت", "ac_back")])
    
    await update.message.reply_text(txt, reply_markup=inline(rows))


# ==================== انتخاب کاربر ====================
async def ac_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    parts = q.data.split(":")
    mode = parts[1]  # gift یا deduct
    uid = int(parts[2])
    
    user = get_user(uid)
    if not user:
        await q.answer("❌ کاربر یافت نشد.", show_alert=True)
        return
    
    name = user["first_name"] or "کاربر"
    
    set_user_state(q.from_user.id, "ac_amount", {"mode": mode, "target_id": uid})
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    if mode == "deduct":
        msg = f"شما در حال کسر سکه از {name} هستید\nلطفا مقدار سکه مورد نظر خود را وارد فرمایید :"
    else:
        msg = f"شما در حال ارسال سکه به {name} هستید\nلطفا مقدار سکه مورد نظر خود را وارد فرمایید :"
    
    await context.bot.send_message(
        q.from_user.id,
        msg,
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
    
    # بازگشت
    if text == "🔙 بازگشت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True
    
    # === جستجوی کاربر ===
    if state == "ac_search_user":
        mode = data.get("mode", "gift")
        await handle_search_user(update, context, text, mode)
        return True
    
    # === دریافت مقدار ===
    if state == "ac_amount":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        
        amount = int(text)
        target_id = data.get("target_id")
        mode = data.get("mode")
        
        if amount <= 0:
            await update.message.reply_text("❌ مقدار باید مثبت باشد.")
            return True
        
        target = get_user(target_id)
        if not target:
            await update.message.reply_text("❌ کاربر یافت نشد.")
            set_user_state(user_id, "none")
            return True
        
        name = target["first_name"] or "کاربر"
        
        set_user_state(user_id, "ac_confirm", {
            "mode": mode, "target_id": target_id, "amount": amount
        })
        
        if mode == "deduct":
            msg = f"آیا از کسر {amount:,} سکه از {name} مطمئن هستید ؟"
        else:
            msg = f"آیا از ارسال {amount:,} سکه به {name} مطمئن هستید ؟"
        
        await update.message.reply_text(
            msg,
            reply_markup=inline([
                [("✅ بله", "ac_confirm_yes"), ("❌ خیر", "ac_back")],
            ])
        )
        return True
    
    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data == "ac_deduct":
        await ac_deduct(update, context)
        return True
    if data == "ac_gift":
        await ac_gift(update, context)
        return True
    if data == "ac_back":
        await ac_back(update, context)
        return True
    if data.startswith("ac_pick:"):
        await ac_pick(update, context)
        return True
    if data == "ac_confirm_yes":
        await ac_confirm_yes(update, context)
        return True
    return False


# ==================== تأیید نهایی ====================
async def ac_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    state, data = get_user_state(user_id)
    if state != "ac_confirm":
        return
    
    mode = data.get("mode")
    target_id = data.get("target_id")
    amount = data.get("amount")
    
    target = get_user(target_id)
    if not target:
        await q.message.reply_text("❌ کاربر یافت نشد.")
        set_user_state(user_id, "none")
        return
    
    name = target["first_name"] or "کاربر"
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    if mode == "deduct":
        success = remove_coins(target_id, amount, "admin_deduct", "کسر توسط مدیریت")
        set_user_state(user_id, "none")
        
        if success:
            await context.bot.send_message(
                user_id,
                f"✅ {amount:,} سکه از {name} کسر شد.",
                reply_markup=admin_panel()
            )
            try:
                await context.bot.send_message(
                    target_id,
                    f"❗️تعداد {amount:,} سکه از حساب شما توسط مدیریت کسر شد."
                )
            except Exception:
                pass
        else:
            await context.bot.send_message(
                user_id,
                "❌ موجودی کاربر کافی نیست.",
                reply_markup=admin_panel()
            )
    else:  # gift
        add_coins(target_id, amount, "admin_gift", "هدیه از طرف مدیریت")
        
        with db.conn() as c:
            c.execute(
                "UPDATE users SET send_coin_admin = send_coin_admin + ? WHERE user_id = ?",
                (amount, target_id)
            )
        
        set_user_state(user_id, "none")
        await context.bot.send_message(
            user_id,
            f"✅ {amount:,} سکه به {name} ارسال شد.",
            reply_markup=admin_panel()
        )
        try:
            await context.bot.send_message(
                target_id,
                f"❗️تعداد {amount:,} سکه از طرف مدیریت به حساب شما واریز شد."
            )
        except Exception:
            pass
