from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from bot_manager import get_user, set_user_state, get_user_state, add_coins, is_admin
from utils.keyboards import main_menu, inline
from utils.helpers import is_positive_int, now_ts

# ==================== کاربر ====================
async def gift_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_user_state(user_id, "gift_code")
    await update.message.reply_text(
        "🎁 کد هدیه خود را ارسال کنید:",
        reply_markup=inline([[("🔙 بازگشت", "back")]])
    )

async def redeem_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import db
    user_id = update.effective_user.id
    code = (update.message.text or "").strip()
    
    with db.conn() as c:
        row = c.execute("SELECT * FROM gift_codes WHERE code = ?", (code,)).fetchone()
        if not row:
            await update.message.reply_text("❌ کد هدیه نامعتبر است.")
            return
        if row["used_by"]:
            await update.message.reply_text("❌ این کد قبلاً استفاده شده.")
            return
        c.execute("UPDATE gift_codes SET used_by=?, used_at=CURRENT_TIMESTAMP WHERE code=?", (user_id, code))
        amount = row["amount"]
    
    add_coins(user_id, amount, "gift", f"کد هدیه: {code}")
    set_user_state(user_id, "none")
    await update.message.reply_text(
        f"🎉 تبریک!\n💰 {amount:,} سکه از کد هدیه دریافت کردید.",
        reply_markup=main_menu(is_admin(user_id))
    )
    
    # اطلاع به کانال هدیه
    from bot_manager import get_setting
    if Config.GIFT_CHANNEL:
        try:
            await context.bot.send_message(
                f"@{Config.GIFT_CHANNEL}",
                f"✅ کد {code} استفاده شد.\n👤 کاربر: {user_id}\n💰 مقدار: {amount}"
            )
        except Exception:
            pass

# ==================== ادمین ====================
async def gift_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot_manager import set_user_state
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "gift_create_code")
    await update.message.reply_text("📝 کد هدیه را وارد کنید:")

async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    from bot_manager import is_admin, set_user_state, get_user_state
    from database import db
    user_id = update.effective_user.id
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    # === کاربر ===
    if state == "gift_code":
        if text == "🔙 بازگشت":
            set_user_state(user_id, "none")
            await update.message.reply_text("🏠", reply_markup=main_menu(is_admin(user_id)))
            return True
        await redeem_gift(update, context)
        return True
    
    # === ادمین ===
    if not is_admin(user_id):
        return False
    
    if state == "gift_create_code":
        set_user_state(user_id, "gift_create_amount", {"code": text})
        await update.message.reply_text("💰 مقدار سکه را وارد کنید:")
        return True
    
    if state == "gift_create_amount":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        code = data.get("code")
        if not code:
            set_user_state(user_id, "none")
            return True
        with db.conn() as c:
            try:
                c.execute("INSERT INTO gift_codes (code, amount) VALUES (?, ?)", (code, int(text)))
            except Exception:
                await update.message.reply_text("❌ این کد قبلاً ساخته شده.")
                set_user_state(user_id, "none")
                return True
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"✅ کد هدیه ساخته شد.\n🎁 کد: {code}\n💰 مقدار: {text}",
            reply_markup=inline([
                [("✅ ارسال به کانال", f"gift_send:{code}")]
            ])
        )
        return True
    
    return False

async def gift_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = q.data.split(":")[1]
    from database import db
    with db.conn() as c:
        row = c.execute("SELECT amount FROM gift_codes WHERE code=?", (code,)).fetchone()
    if not row:
        return
    if not Config.GIFT_CHANNEL:
        await q.message.reply_text("❌ کانال هدیه تنظیم نشده.")
        return
    try:
        await context.bot.send_message(
            f"@{Config.GIFT_CHANNEL}",
            f"🎁 کد هدیه جدید!\n\n🏷 کد: {code}\n💰 مقدار: {row['amount']:,} سکه\n\n"
            f"⏰ همین حالا در ربات استفاده کنید!",
            reply_markup=inline([[("🚀 ورود به ربات", f"https://t.me/{(await context.bot.get_me()).username}")]])
        )
        await q.message.edit_text("✅ کد به کانال ارسال شد.")
    except Exception as e:
        await q.message.reply_text(f"❌ خطا: {e}")