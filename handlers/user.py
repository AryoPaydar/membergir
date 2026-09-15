from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from config import Config
from bot_manager import (
    get_user, create_user, update_user, set_user_state, get_user_state,
    add_coins, get_daily_gift, is_admin, is_banned, check_membership
)
from utils.keyboards import main_menu, back_button, inline
from utils.texts import start_text, account_text
from utils.helpers import now_ts, jalali_now

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message
    args = context.args
    
    # بررسی بن
    if is_banned(user.id):
        await msg.reply_text("⛔️ شما از ربات مسدود شده‌اید.")
        return
    
    # چک قدرت ربات
    from bot_manager import is_bot_on, get_setting
    if not is_bot_on() and not is_admin(user.id):
        text = get_setting("power_text", "ربات در حال حاضر خاموش است.")
        await msg.reply_text(text)
        return
    
    # ساخت یا دریافت کاربر
    db_user = get_user(user.id)
    referrer_id = None
    if not db_user and args:
        try:
            ref = int(args[0])
            if ref != user.id and get_user(ref):
                referrer_id = ref
        except (ValueError, IndexError):
            pass
    
    if not db_user:
        db_user = create_user(user.id, user.first_name or "", user.username or "", referrer_id)
        if referrer_id:
            await handle_referral_join(context, referrer_id, user.id)
    else:
        update_user(user.id, first_name=user.first_name or "", username=user.username or "")
        update_user(user.id, state="none")
        
        # ریست شمارنده‌های روزانه اگه روز عوض شده
        today, _ = jalali_now()
        if db_user.get("today_date") != today:
            with db.conn() as c:
                c.execute("""
                    UPDATE users
                    SET today_earned = 0, referral_today = 0, today_date = ?
                    WHERE user_id = ?
                """, (today, user.id))
    
    # چک جوین اجباری
    if not await check_force_join(context, user.id):
        return
    
    await msg.reply_text(
        start_text(user.first_name, user.id),
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(user.id))
    )

async def check_force_join(context, user_id):
    """چک عضویت اجباری — اگه کاربر عضو نبود، پیام بده"""
    missing = []
    for ch in (Config.FORCE_CHANNEL_1, Config.FORCE_CHANNEL_2):
        if ch and not await check_membership(context, ch, user_id):
            missing.append(ch)
    
    if not missing:
        return True
    
    text = "🔐 برای استفاده از ربات ابتدا در کانال‌های زیر عضو شوید:\n\n"
    buttons = []
    for ch in missing:
        text += f"📢 @{ch}\n"
        buttons.append([(f"عضویت در @{ch}", f"https://t.me/{ch}")])
    buttons.append([("✅ عضو شدم", "check_join")])
    
    from telegram import InlineKeyboardMarkup
    await context.bot.send_message(
        user_id, text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return False

async def handle_referral_join(context, referrer_id, new_user_id):
    """پاداش زیرمجموعه جدید"""
    referrer = get_user(referrer_id)
    if not referrer:
        return
    from bot_manager import get_invite_coin, add_coins, get_setting
    
    coin = get_invite_coin(referrer)
    add_coins(referrer_id, coin, "referral", f"زیرمجموعه جدید: {new_user_id}")
    
    # افزایش شمارنده امروز
    with db.conn() as c:
        c.execute(
            "UPDATE users SET referral_today = referral_today + 1 WHERE user_id = ?",
            (referrer_id,)
        )
    
    try:
        await context.bot.send_message(
            referrer_id,
            f"🎉 یک کاربر جدید با لینک شما عضو ربات شد!\n"
            f"💰 {coin} سکه به حساب شما اضافه شد."
        )
    except Exception:
        pass
    
    if get_setting("referral_report", "on") == "on":
        try:
            await context.bot.send_message(
                Config.ADMIN_ID,
                f"📢 گزارش زیرمجموعه\n👤 کاربر {new_user_id} با لینک {referrer_id} عضو شد."
            )
        except Exception:
            pass

# ==================== حساب کاربری ====================
async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("لطفاً /start را بزنید.")
        return
    
    text = account_text(user)
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=inline([[("🔗 اشتراک آیدی من", f"share_id")]])
    )

# ==================== دریافت سکه (منوی الماس رایگان) ====================
async def daily_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("لطفاً /start را بزنید.")
        return
    
    text = (
        "به بخش دریافت الماس رایگان خوش آمدید🌹\n"
        "\n"
        "📌در این بخش میتونید با استفاده از سه روش زیر برای خودتون الماس جمع آوری کنید سپس با الماس های جمع آوری شده برای کانال/گروه خود ممبر سفارش بدید.\n"
        "\n"
        "\n"
        "👈 سه روش برای جمع آوری الماس وجود دارد:\n"
        "\n"
        "1⃣ دریافت الماس روزانه: با استفاده از بخش میتوانید در ربات با زدن یک دکمه مقدار 3 الماس دریافت کنید.\n"
        "\n"
        "2⃣ عضویت در سفارش های موجود: در این روش شما میتوانید با عضویت در سفارشات موجود و سپس زدن دکمه ی دریافت  اقدام به جمع آوری الماس نمایید.\n"
        "\n"
        "3️⃣ خرید الماس : شما میتوانید با خرید الماس به سادگی و بدون عضویت مقدار ممبر مورد نیاز خود را تهیه فرمایید.\n"
        "\n"
        "🫂 همچنین از طریق زیر مجموعه گیری هم میتونید تا بینهایت الماس رایگان کسب کنید.\n"
    )
    
    ads_channel = Config.ADS_CHANNEL or ""
    
    keyboard = inline([
        [("📢 عضویت در کانال", f"https://t.me/{ads_channel}")],
        [("💎 الماس روزانه", "daily_gift_claim")],
        [("🛍 خرید الماس", "go_to_shop")],
    ])
    
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ==================== کلیک روی دکمه الماس روزانه ====================
async def daily_gift_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    user = get_user(user_id)
    if not user:
        await q.answer("❌ لطفاً ابتدا /start را بزنید.", show_alert=True)
        return
    
    now = now_ts()
    cooldown = Config.DAILY_GIFT_COOLDOWN
    last_daily = user.get("last_daily") or 0
    next_time = last_daily + cooldown
    
    if now < next_time:
        remaining = next_time - now
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        time_str = f"{hours:02d}:{minutes:02d}"
        
        await q.answer(
            f"⏳ شما قبلاً هدیه امروز را دریافت کرده‌اید.\n"
            f"🕐 زمان باقی‌مانده: {time_str}",
            show_alert=True
        )
        return
    
    amount = get_daily_gift(user)
    add_coins(user_id, amount, "daily", "هدیه روزانه")
    update_user(user_id, last_daily=now)
    
    new_user = get_user(user_id)
    new_balance = new_user.get("coins", 0)
    
    await q.answer(
        f"🎉 تبریک!\n"
        f"💰 {amount} سکه به حساب شما اضافه شد.\n"
        f"💳 موجودی جدید: {new_balance:,}",
        show_alert=True
    )

# ==================== دکمه خرید الماس ====================
async def go_to_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    # مستقیم پنل فروشگاه رو باز کن
    from handlers import shop
    await shop.shop_menu_from_callback(update, context)
    
# ==================== بازگشت به منو ====================
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user(user.id, state="none", state_data=None)
    await update.message.reply_text(
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(user.id))
    )

# ==================== اشتراک آیدی ====================
async def share_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    await q.message.reply_text(
        f"🆔 آیدی عددی شما:\n<code>{user_id}</code>",
        parse_mode="HTML"
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if await check_force_join(context, user_id):
        try:
            await q.message.delete()
        except Exception:
            pass
        user = get_user(user_id)
        if user:
            await context.bot.send_message(
                user_id,
                "✅ عضویت شما تأیید شد. حالا /start را بزنید.",
                reply_markup=main_menu(is_admin(user_id))
            )
    else:
        await q.answer("❌ هنوز عضو نشده‌اید!", show_alert=True)

# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """روتر callback برای user.py"""
    q = update.callback_query
    data = q.data
    
    if data == "share_id":
        await share_id(update, context)
        return True
    if data == "check_join":
        await check_join_callback(update, context)
        return True
    if data == "daily_gift_claim":
        await daily_gift_claim(update, context)
        return True
    if data == "go_to_shop":
        await go_to_shop(update, context)
        return True
    if data == "back":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        return True
    return False

# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """این ماژول state ندارد."""
    return False
