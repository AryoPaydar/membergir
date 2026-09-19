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
    set_user_state(q.from_user.id, "ac_deduct_input")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "📍 لطفا در خط اول ایدی فرد و در خط دوم میزان موجودی را وارد کنید\n\n"
        "مثال:\n"
        "267785153\n"
        "20",
        reply_markup=back_button()
    )


async def ac_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "ac_gift_input")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "📍 لطفا در خط اول ایدی فرد و در خط دوم میزان موجودی را وارد کنید\n\n"
        "مثال:\n"
        "267785153\n"
        "20",
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
    
    if state == "ac_deduct_input":
        lines = text.split("\n")
        if len(lines) < 2:
            await update.message.reply_text("❌ لطفا در دو خط ارسال کنید.")
            return True
        try:
            target_id = int(lines[0].strip())
            amount = int(lines[1].strip())
        except ValueError:
            await update.message.reply_text("❌ فقط اعداد مجاز هستند.")
            return True
        if amount <= 0:
            await update.message.reply_text("❌ مقدار باید مثبت باشد.")
            return True
        
        target = get_user(target_id)
        if not target:
            await update.message.reply_text("❌ کاربر یافت نشد.")
            set_user_state(user_id, "none")
            return True
        
        success = remove_coins(target_id, amount, "admin_deduct", "کسر توسط مدیریت")
        set_user_state(user_id, "none")
        
        if success:
            await update.message.reply_text(
                "✅ کسر موجودی با موفقیت انجام شد",
                reply_markup=admin_panel()
            )
            try:
                await context.bot.send_message(
                    target_id,
                    f'''❗️تعداد {amount:,} سکه از حساب شما توسط مدیریت کسر شد.'''
                )
            except Exception:
                pass
        else:
            await update.message.reply_text(
                "❌ موجودی کاربر کافی نیست.",
                reply_markup=admin_panel()
            )
        return True
    
    if state == "ac_gift_input":
        lines = text.split("\n")
        if len(lines) < 2:
            await update.message.reply_text("❌ لطفا در دو خط ارسال کنید.")
            return True
        try:
            target_id = int(lines[0].strip())
            amount = int(lines[1].strip())
        except ValueError:
            await update.message.reply_text("❌ فقط اعداد مجاز هستند.")
            return True
        if amount <= 0:
            await update.message.reply_text("❌ مقدار باید مثبت باشد.")
            return True
        
        target = get_user(target_id)
        if not target:
            await update.message.reply_text("❌ کاربر یافت نشد.")
            set_user_state(user_id, "none")
            return True
        
        add_coins(target_id, amount, "admin_gift", "هدیه از طرف مدیریت")
        
        # افزایش send-coin-admin
        with db.conn() as c:
            c.execute(
                "UPDATE users SET send_coin_admin = send_coin_admin + ? WHERE user_id = ?",
                (amount, target_id)
            )
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            "✅ افزایش موجودی با موفقیت انجام شد",
            reply_markup=admin_panel()
        )
        try:
            await context.bot.send_message(
                target_id,
                f"❗️تعداد {amount:,} سکه از طرف مدیریت به حساب شما واریز شد."
            )
        except Exception:
            pass
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
    return False
