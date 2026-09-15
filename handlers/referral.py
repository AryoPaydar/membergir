from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from bot_manager import get_user, get_setting, get_user_state, get_panel_config
from utils.keyboards import inline, back_button, main_menu
from utils.helpers import is_positive_int

# ==================== منوی زیرمجموعه‌گیری ====================
async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("لطفاً /start را بزنید.")
        return
    
    # چک تنظیمات
    if get_setting("referral_enabled", "on") != "on":
        await update.message.reply_text("❌ زیرمجموعه‌گیری غیرفعال است.")
        return
    
    # مقادیر پنل‌ها از Config
    normal_invite = Config.PANELS["عادی"]["invite_coin"]
    pro_invite = Config.PANELS["حرفه ای"]["invite_coin"]
    vip_invite = Config.PANELS["ویژه"]["invite_coin"]
    
    # درصد پورسانت (فرضی - از تنظیمات یا ثابت)
    normal_percent = 5
    pro_percent = 10
    vip_percent = 15
    
    ads_channel = Config.ADS_CHANNEL or ""
    
    text = (
        f"پنل معمولی(🥉):\n"
        f"(❗️برای همه کاربران فعال هست!)\n"
        f"💎الماس زیرمجموعه گیری : {normal_invite}\n"
        f"🎉پورسانت : {normal_percent} درصد\n"
        f"\n"
        f"پنل حرفه ای(🥈):\n"
        f"(❗️جهت خرید از فروشگاه اقدام کنید!)\n"
        f"💎الماس زیرمجموعه گیری : {pro_invite}\n"
        f"🎉پورسانت : {pro_percent} درصد\n"
        f"\n"
        f"پنل ویژه(🥇): \n"
        f"(❗️جهت خرید از فروشگاه اقدام کنید!)\n"
        f"💎الماس زیرمجموعه گیری : {vip_invite}\n"
        f"🎉پورسانت : {vip_percent} درصد\n"
        f"\n"
        f"❗️برای اینکه ربات تشخیص بده زیر مجموعه ی شما فیک نیست باید زیرمجموعه تون در سه کانال یا گروه که سفارش دادن (در @{ads_channel})  عضو بشه و روی  دکمه دریافت الماسِ 3 تا سفارش بزنه تا توسط ربات تایید بشه و الماس رو به حساب شما واریز کنه!\n"
        f"⚠️در صورت مشاهده زیر مجموعه گیری فیک فرد بدون در نظر گرفتن موجودی برای همیشه مسدود می شود.\n"
        f"\n"
        f"🫂جهت دریافت لینک زیر مجموعه گیری خود روی دکمه زیر کلیک کنید👇"
    )
    
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔰 دریافت بنر زیرمجموعه گیری", "share_referral_banner")],
            [("🔙 بازگشت", "referral_back")],
        ])
    )


# ==================== دکمه ارسال بنر ====================
async def share_referral_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    user = get_user(user_id)
    first_gift = Config.PANELS["عادی"]["invite_coin"] if user else 15
    
    text = (
        f"🚀 با ممبرگیر هایو به راحتی اعضای کانال و گروه خود را بصورت (رایگان؛پولی) افزایش دهید!\n"
        f"👥 افزایش اعضای کانال و گروه شما\n"
        f"🇮🇷 دریافت ممبر ایرانی کاملا واقعی و فعال\n"
        f"🎁 دریافت هدیه {first_gift} الماس برای اولین ورود شما\n"
        f"⚡️ سریع و بدون آفلاینی\n"
        f"💯اگه اعضای کانال و گروهت کمه امتحان کن👇\n"
        f"{ref_link}"
    )
    
    # ارسال به صورت اینلاین (برای فوروارد راحت)
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("📢 اشتراک‌گذاری", f"https://t.me/share/url?url={ref_link}&text=به ممبرگیر هایو بپیوندید!")],
            [("🔙 بازگشت", "referral_back")],
        ])
    )


# ==================== بازگشت به منوی اصلی ====================
async def referral_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    
    from bot_manager import is_admin
    await context.bot.send_message(
        q.from_user.id,
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(q.from_user.id))
    )


# ==================== تنظیمات ادمین ====================
async def referral_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot_manager import is_admin
    if not is_admin(update.effective_user.id):
        return
    enabled = get_setting("referral_enabled", "on")
    report = get_setting("referral_report", "on")
    banner = get_setting("referral_banner_type", "text")
    threshold = get_setting("referral_join_threshold", str(Config.REFERRAL_JOIN_THRESHOLD))
    coin = get_setting("referral_join_coin", str(Config.REFERRAL_JOIN_COIN))
    
    await update.message.reply_text(
        "⚙️ تنظیمات زیرمجموعه‌گیری",
        reply_markup=inline([
            [(f"وضعیت: {'روشن ✅' if enabled=='on' else 'خاموش ❌'}", "ref_toggle")],
            [(f"گزارش: {'روشن ✅' if report=='on' else 'خاموش ❌'}", "ref_toggle_report")],
            [(f"نوع بنر: {banner}", "ref_toggle_banner")],
            [(f"آستانه عضویت: {threshold}", "ref_set_threshold")],
            [(f"سکه پورسانت: {coin}", "ref_set_coin")],
            [("📝 تنظیم متن", "ref_set_text")],
            [("🖼 تنظیم عکس", "ref_set_photo")],
        ])
    )


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    
    # === دکمه‌های زیرمجموعه‌گیری ===
    if data == "referral_banner":
        await referral_banner(update, context)
        return True
    if data == "share_referral_banner":
        await share_referral_banner(update, context)
        return True
    if data == "referral_back":
        await referral_back(update, context)
        return True
    
    # === دکمه‌های تنظیمات ادمین ===
    from bot_manager import is_admin, set_setting, get_setting, set_user_state
    if not is_admin(q.from_user.id):
        return False
    
    if data == "ref_toggle":
        cur = get_setting("referral_enabled", "on")
        set_setting("referral_enabled", "off" if cur == "on" else "on")
        await q.answer("✅ تغییر کرد")
        await referral_admin(update, context)
        return True
    if data == "ref_toggle_report":
        cur = get_setting("referral_report", "on")
        set_setting("referral_report", "off" if cur == "on" else "on")
        await q.answer("✅")
        await referral_admin(update, context)
        return True
    if data == "ref_toggle_banner":
        cur = get_setting("referral_banner_type", "text")
        set_setting("referral_banner_type", "photo" if cur == "text" else "text")
        await q.answer("✅")
        await referral_admin(update, context)
        return True
    if data == "ref_set_threshold":
        set_user_state(q.from_user.id, "ref_set_threshold")
        await q.message.reply_text("👈 آستانه عضویت را وارد کنید:")
        return True
    if data == "ref_set_coin":
        set_user_state(q.from_user.id, "ref_set_coin")
        await q.message.reply_text("👈 تعداد سکه پورسانت را وارد کنید:")
        return True
    if data == "ref_set_text":
        set_user_state(q.from_user.id, "ref_set_text")
        await q.message.reply_text("📝 متن بنر را ارسال کنید:")
        return True
    if data == "ref_set_photo":
        set_user_state(q.from_user.id, "ref_set_photo")
        await q.message.reply_text("🖼 عکس بنر را ارسال کنید:")
        return True
    return False


# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    from bot_manager import is_admin, set_setting, set_user_state
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    state, _ = get_user_state(user_id)
    
    if state == "ref_set_threshold":
        if is_positive_int(update.message.text):
            set_setting("referral_join_threshold", update.message.text.strip())
            set_user_state(user_id, "none")
            await update.message.reply_text("✅")
            return True
    if state == "ref_set_coin":
        if is_positive_int(update.message.text):
            set_setting("referral_join_coin", update.message.text.strip())
            set_user_state(user_id, "none")
            await update.message.reply_text("✅")
            return True
    if state == "ref_set_text":
        set_setting("referral_text", update.message.text)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅")
        return True
    if state == "ref_set_photo" and update.message.photo:
        set_setting("referral_photo_id", update.message.photo[-1].file_id)
        set_user_state(user_id, "none")
        await update.message.reply_text("✅")
        return True
    return False
