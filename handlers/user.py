from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from config import Config
from bot_manager import (
    get_user, create_user, update_user, set_user_state, get_user_state,
    add_coins, get_daily_gift, is_admin, is_banned, check_membership,
    get_panel_config
)
from utils.keyboards import main_menu, back_button, inline, rules_back_keyboard
from utils.texts import start_text, account_text
from utils.helpers import now_ts, jalali_now


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.message
    args = context.args
    
    if is_banned(user.id):
        await msg.reply_text("⛔️ شما از ربات مسدود شده‌اید.")
        return
    
    from bot_manager import is_bot_on, get_setting
    if not is_bot_on() and not is_admin(user.id):
        text = get_setting("power_text", "ربات در حال حاضر خاموش است.")
        await msg.reply_text(text)
        return
    
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
        
        today, _ = jalali_now()
        if db_user.get("today_date") != today:
            with db.conn() as c:
                c.execute("""
                    UPDATE users
                    SET today_earned = 0, referral_today = 0, today_date = ?
                    WHERE user_id = ?
                """, (today, user.id))
    
    if not await check_force_join(context, user.id):
        return
    
    await msg.reply_text(
        start_text(user.first_name, user.id),
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(user.id))
    )


async def check_force_join(context, user_id):
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
    referrer = get_user(referrer_id)
    if not referrer:
        return
    
    panel_cfg = get_panel_config(referrer.get("panel", "عادی"))
    invite_coin = panel_cfg["invite_coin"]
    commission_percent = {
        "عادی": 5,
        "حرفه ای": 10,
        "ویژه": 15,
    }.get(referrer.get("panel", "عادی"), 5)
    
    try:
        await context.bot.send_message(
            referrer_id,
            f"🎉اطلاعیه زیرمجموعه جدید\n"
            f"\n"
            f"✅یک کاربر با لینک اختصاصی شما عضو ربات شد\n"
            f"\n"
            f"👈 پس از دریافت 3 الماس(عضویت در کانال) توسط زیرمجموعه ی شما ، {invite_coin} الماس به حساب شما واریز می شود\n"
            f"\n"
            f"👌همچنین {commission_percent} درصد از پورسانت حاصل از فعالیت کاربر به طور دائمی به شما تعلق گرفت",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    from bot_manager import get_setting
    if get_setting("referral_report", "on") == "on":
        try:
            await context.bot.send_message(
                Config.ADMIN_ID,
                f"📢 گزارش زیرمجموعه\n👤 کاربر {new_user_id} با لینک {referrer_id} عضو شد."
            )
        except Exception:
            pass


async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("لطفاً /start را بزنید.")
        return
    
    text = account_text(user)
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=inline([
            [("🎊 دریافت هدیه ساعتی", "hourly_gift_claim")],
            [("🔗 اشتراک آیدی من", "share_id")],
        ])
    )


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


async def hourly_gift_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    user = get_user(user_id)
    if not user:
        await q.answer("❌ لطفاً ابتدا /start را بزنید.", show_alert=True)
        return
    
    now = now_ts()
    cooldown = Config.HOURLY_GIFT_COOLDOWN
    last_hourly = user.get("last_hourly") or 0
    next_time = last_hourly + cooldown
    
    if now < next_time:
        remaining = next_time - now
        minutes = remaining // 60
        seconds = remaining % 60
        await q.answer(
            f"⏳ زمان باقی‌مانده: {minutes} دقیقه و {seconds} ثانیه",
            show_alert=True
        )
        return
    
    amount = Config.HOURLY_GIFT_AMOUNT
    add_coins(user_id, amount, "hourly_gift", "هدیه ساعتی")
    update_user(
        user_id,
        last_hourly=now,
        hourly_earned=(user.get("hourly_earned", 0) + amount)
    )
    
    new_user = get_user(user_id)
    new_balance = new_user.get("coins", 0)
    
    await q.answer(
        f"🎉 تبریک!\n"
        f"💰 {amount} سکه هدیه ساعتی دریافت کردید.\n"
        f"💳 موجودی جدید: {new_balance:,}",
        show_alert=True
    )


async def go_to_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    from handlers import shop
    await shop.shop_menu_from_callback(update, context)


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user(user.id, state="none", state_data=None)
    await update.message.reply_text(
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(user.id))
    )


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


# ==================== ⚖️ قوانین ====================
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "به بخش ⚖️ قوانین ممبرگیر هایو خوش آمدید.\n"
        "\n"
        "❗️ نکات مهم (با دقت بخوانید)❗️ :\n"
        "📍وقتی توی سفارش ها عضو میشید و الماس میگیرین نباید کمتر از 3 روز لفت بدین چون الماس کسر میشه ازتون. پس باید 3 روز کامل صبر کنید و روز چهارم میتونید لفت بدین.\n"
        "⚠️ثبت سفارش کانال ممبر گیر، سین گیر، فروش الماس ربات، مسائل سیاسی و مذهبی و کانال +18 باعث مسدود شدن همیشگی حساب و کانالتان می شود.\n"
        "⚠️اگر سفارش در حال انجام دارین ایدی مقصد رو تغییر ندید یا ربات رو از ادمینی خارج نکنید چون سایر افراد میتونن بدون عضویت سفارش شما رو تکمیل کنن و در حقتون اجحاف میشه.\n"
        "⚠️ به هیچ وجه پشت سرهم چند تا سفارش ندین چون ناتمام تکمیل میشن.\n"
        "و سفارش هایی که مشکل دارن پاک میشن و همچنین گروه هایی که درخواست عضویت شون فعاله لغو میشه و سفارش دهنده مسدود میشه از ربات!\n"
        "⚠️ همچنین ما هیچ مسئولیتی در قبال کانال و گروه های تبلیغ شده نداریم.\n"
        "\n"
        "❌به هیچ عنوان  از باگ های احتمالی ربات سو استفاده نکنید\n"
        "❗️ کسایی که اخطار میگیرن یا مسدود میشن به هیچ وجه بخشیده نمیشن!\n"
        "\n"
        "❗️❗️توجه داشته باشید قبل از ثبت سفارش \n"
        "ربات باید ادمین کانال یا گروه تون باشه.\n"
        "\n"
        "✅کلیه پرداخت های کارت به کارت توسط پشتیبانی ربات ( @Eror_500 ) انجام می شود.\n"
        "✅ بعد از پرداخت هزینه ، بسته مورد نظر توسط پشتیبانی به حساب شما واریز خواهد شد.\n"
        "جهت مشاوره یا سوال و خرید به پشتیبانی مراجعه کنید👇"
    )
    await update.message.reply_text(
        text,
        reply_markup=rules_back_keyboard()
    )


# ==================== 💡 راهنما ====================
async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💡 به بخش راهنمای استفاده از ربات خوش آمدید\n"
        "\n"
        "لطفا از دکمه های زیر سوال خود را پیدا کنید.\n"
        "همچنین میتوانید در صورت داشتن هر گونه سوال با مدیریت در ارتباط باشید."
    )
    
    keyboard = inline([
        [("💎 نحوه جمع آوری الماس", "help_collect")],
        [("🛍 نحوه استفاده از فروشگاه", "help_shop")],
        [("🚀 نحوه ثبت سفارش", "help_order")],
        [("📋 نحوه پیگیری سفارش", "help_tracking")],
        [("🎁 نحوه استفاده از کد هدیه", "help_gift")],
        [("🏦 نحوه انتقال الماس", "help_transfer")],
        [("🔙 بازگشت به منوی اصلی", "help_back")],
    ])
    
    await update.message.reply_text(text, reply_markup=keyboard)


# ==================== بخش‌های راهنما ====================
async def help_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "💎 <b>نحوه جمع آوری الماس</b>\n"
        "\n"
        "برای جمع آوری الماس به صورت رایگان دو روش وجود دارد :\n"
        "\n"
        "1️⃣ <b>استفاده از سکه روزانه :</b>\n"
        "کاربران میتوانند در هر 24 ساعت 1 بار از قسمت 💰 دریافت الماس و با زدن گزینه 💎 الماس روزانه، با توجه به پنلشان مقداری الماس دریافت نمایند.\n"
        "\n"
        "2️⃣ <b>دریافت از طریق عضویت در کانال :</b>\n"
        "کاربران میتوانند از قسمت 💰 دریافت الماس و با زدن گزینه 📢 عضویت در کانال میتوانید ابتدا عضو کانال شود و با زدن دکمه دریافت الماس، متناسب با پنل خود، الماس دریافت نمایید.\n"
        "\n"
        "⚠️ لازم به ذکر است در صورت عضویت در کانال و دریافت سکه الزاما باید 3 روز در کانال بمانند در غیر این صورت سکه های دریافتی به عنوان جریمه مسترد میشود."
    )
    
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔙 بازگشت", "help_main")]
        ])
    )


async def help_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "🛍 <b>نحوه استفاده از فروشگاه</b>\n"
        "\n"
        "کاربران برای خرید الماس یا خرید پنل از بخش 🛍 فروشگاه اقدام نمایند.\n"
        "\n"
        "لازم به توضیح برای استفاده از بخش فروشگاه ابتدا باید شماره موبایل خود را وارد نمایند.\n"
        "\n"
        "⚠️ البته لازم به ذکر است که شماره شما نزد ما محفوظ است و هیچ شخصی به آن دسترسی نخواهد داشت."
    )
    
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔙 بازگشت", "help_main")]
        ])
    )


async def help_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "🚀 <b>نحوه ثبت سفارش</b>\n"
        "\n"
        "برای ثبت سفارش تنها کافی است که ربات رو در کانال یا گروه خود ادمین کنید و سپس از بخش 🚀 ثبت سفارش مقدار ممبر مورد نیاز خود را سفارش دهند.\n"
        "\n"
        "⚠️ به خاطر داشته باشید که چنانچه ربات ادمین کانال یا گروه شما نباشد یا ایدی کانال یا گروه شما تغییر پیدا کند، سایر کاربران میتوانند بدون عضویت در کانال شما با زدن دریافت سکه، سفارش شما را تکمیل نمایند."
    )
    
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔙 بازگشت", "help_main")]
        ])
    )


async def help_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "📋 <b>نحوه پیگیری سفارش</b>\n"
        "\n"
        "در منوی کاربری با زدن دکمه 📋 پیگیری سفارش میتوانید گزارش سفارش هایی که انجام دادید را دریافت نمایید.\n"
        "\n"
        "این گزارش شامل تعداد اعضای ورود و خروجی به کانال یا گروه شما میباشد.\n"
        "\n"
        "همچنین در این بخش میتوانید سفارش خود را کنسل و با توجه به مقدار کاربران دریافتی، مابقی الماس های خود را مسترد نمایید."
    )
    
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔙 بازگشت", "help_main")]
        ])
    )


async def help_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "🎁 <b>نحوه استفاده از کد هدیه</b>\n"
        "\n"
        "در پنل کاربری با استفاده از دکمه 🎁 کد هدیه میتوانید با وارد کردن کد هدیه، هدیه خود را دریافت نمایید.\n"
        "\n"
        "⚠️ توجه داشته باشید که دو نوع هدیه وجود دارد:\n"
        "\n"
        "1️⃣ <b>هدیه دائمی :</b>\n"
        "این نوع از هدیه مستقیما وارد حساب کاربری شما میشود و هر زمان بخواهید میتوانید از آن استفاده نمایید یا به دیگران انتقال دهید.\n"
        "شما میتوانید مقدار این هدیه را در حساب کاربری و قسمت 🎁 هدیه مدیریت مشاهده فرمایید.\n"
        "\n"
        "2️⃣ <b>هدیه اعتباری :</b>\n"
        "این نوع از هدیه باید در مدت زمان مقرر مصرف شود وگرنه از حساب کاربری شما کسر خواهد شد. همچنین این هدیه قابلیت انتقال به کاربران دیگر را ندارد.\n"
        "شما میتوانید مقدار و زمان باقی مانده این هدیه را در حساب کاربری و قسمت 🎊 هدیه اعتباری و ⏳ زمان باقی مانده هدیه اعتباری مشاهده فرمایید."
    )
    
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔙 بازگشت", "help_main")]
        ])
    )


async def help_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "🏦 <b>نحوه انتقال الماس</b>\n"
        "\n"
        "شما میتوانید الماس های خود را به هر کاربر دیگر که تمایل داشتید انتقال دهید.\n"
        "\n"
        "برای اینکار کافیست از منوی کاربری، دکمه 🏦 بانک انتقال را بزنید و سپس 💎 انتقال الماس را انتخاب نمایید تا با وارد کردن شماره کاربری فرد مورد نظر و تایید انتقال، مقدار الماس مورد نظر خود را به دیگران انتقال دهید."
    )
    
    await q.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔙 بازگشت", "help_main")]
        ])
    )


async def help_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    text = (
        "💡 به بخش راهنمای استفاده از ربات خوش آمدید\n"
        "\n"
        "لطفا از دکمه های زیر سوال خود را پیدا کنید.\n"
        "همچنین میتوانید در صورت داشتن هر گونه سوال با مدیریت در ارتباط باشید."
    )
    
    try:
        await q.message.edit_text(
            text,
            reply_markup=inline([
                [("💎 نحوه جمع آوری الماس", "help_collect")],
                [("🛍 نحوه استفاده از فروشگاه", "help_shop")],
                [("🚀 نحوه ثبت سفارش", "help_order")],
                [("📋 نحوه پیگیری سفارش", "help_tracking")],
                [("🎁 نحوه استفاده از کد هدیه", "help_gift")],
                [("🏦 نحوه انتقال الماس", "help_transfer")],
                [("🔙 بازگشت به منوی اصلی", "help_back")],
            ])
        )
    except Exception:
        pass


async def help_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(q.from_user.id))
    )


# ==================== 📨 ارتباط با مدیریت ====================
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot_manager import get_setting
    text = get_setting("contact_text",
        "📨 <b>ارتباط با مدیریت:</b>\n\n"
        "برای ارتباط با مدیریت ربات، از طریق آیدی زیر پیام دهید:\n\n"
        "👤 ادمین: @YourAdmin"
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(update.effective_user.id))
    )


# ==================== 💞 حمایت مالی ====================
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot_manager import get_setting
    text = get_setting("support_text",
        "💞 <b>حمایت مالی از ربات:</b>\n\n"
        "از حمایت شما سپاسگزاریم 🙏\n\n"
        "💳 شماره کارت: <code>0000-0000-0000-0000</code>\n"
        "👤 به نام: مدیر ربات"
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(update.effective_user.id))
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
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
    if data == "hourly_gift_claim":
        await hourly_gift_claim(update, context)
        return True
    if data == "go_to_shop":
        await go_to_shop(update, context)
        return True
    if data == "help_collect":
        await help_collect(update, context)
        return True
    if data == "help_shop":
        await help_shop(update, context)
        return True
    if data == "help_order":
        await help_order(update, context)
        return True
    if data == "help_tracking":
        await help_tracking(update, context)
        return True
    if data == "help_gift":
        await help_gift(update, context)
        return True
    if data == "help_transfer":
        await help_transfer(update, context)
        return True
    if data == "help_main":
        await help_main(update, context)
        return True
    if data == "help_back":
        await help_back(update, context)
        return True
    if data == "back":
        await q.answer()
        try:
            await q.message.delete()
        except Exception:
            pass
        return True
    return False


async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """این ماژول state ندارد — ولی gift state رو پاس میدیم."""
    from handlers import gift
    if await gift.handle_state(update, context):
        return True
    return False
