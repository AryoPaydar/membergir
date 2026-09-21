import os
from dotenv import load_dotenv

# لود .env (اگه وجود داشته باشه — برای تست لوکال)
load_dotenv()


class Config:
    # === تنظیمات اصلی ===
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBot")
    
    # === دیتابیس ===
    DB_PATH = os.getenv("DB_PATH", "bot.db")
    
    # === کانال‌ها (بدون @) ===
    ADS_CHANNEL = os.getenv("ADS_CHANNEL", "")
    GIFT_CHANNEL = os.getenv("GIFT_CHANNEL", "")
    FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1", "")
    FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2", "")
    
    # === تنظیمات پیش‌فرض ===
    DEFAULT_COINS = 20
    DEFAULT_PANEL = "عادی"
    MAX_WARNINGS = 3
    DAILY_GIFT_COOLDOWN = 86400
    HOURLY_GIFT_COOLDOWN = 1800
    HOURLY_GIFT_AMOUNT = 1
    
    # === پنل‌ها ===
    PANELS = {
        "عادی":     {"daily": 3, "join_coin": 1.5, "invite_coin": 10,  "upgrade_cost": 0},
        "حرفه ای":  {"daily": 4, "join_coin": 2, "invite_coin": 15, "upgrade_cost": 100},
        "ویژه":     {"daily": 5, "join_coin": 2.5, "invite_coin": 20, "upgrade_cost": 200},
    }
    
    # === تنظیمات انتقال ===
    TRANSFER_MIN = 10
    TRANSFER_MAX = 1000
    TRANSFER_ENABLED = True
    
    # === تنظیمات لغو سفارش ===
    CANCEL_ENABLED = True
    CANCEL_MIN_MEMBERS = 100
    CANCEL_WAIT_SECONDS = 60
    CANCEL_REFUND_RATIO = 0.5
    
    # === تنظیمات ترک کانال ===
    LEAVE_CHECK_DAYS = 7
    LEAVE_PENALTY = 5
    LEAVE_REWARD = 3
    
    # === زیرمجموعه ===
    REFERRAL_ENABLED = True
    REFERRAL_REPORT = True
    REFERRAL_JOIN_THRESHOLD = 10
    REFERRAL_JOIN_COIN = 5
    REFERRAL_BANNER_TYPE = "text"
    
    # === قدرت ربات ===
    BOT_POWER = True
    POWER_OFF_TEXT = "ربات در حال حاضر خاموش است."


# ==================== بررسی متغیرهای حیاتی ====================
def _validate_config():
    """بررسی متغیرهای حیاتی — اگه نبودن، خطای واضح بده"""
    errors = []
    
    if not Config.BOT_TOKEN:
        errors.append(
            "❌ BOT_TOKEN تنظیم نشده!\n"
            "   → در Render: Environment → Add Environment Variable\n"
            "   → Key: BOT_TOKEN\n"
            "   → Value: توکن از @BotFather"
        )
    elif Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        errors.append(
            "❌ BOT_TOKEN هنوز مقدار پیش‌فرض YOUR_BOT_TOKEN_HERE است!\n"
            "   → در Render: Environment → BOT_TOKEN را اصلاح کن\n"
            "   → توکن جدید از @BotFather بگیر"
        )
    elif ":" not in Config.BOT_TOKEN:
        errors.append(
            "❌ BOT_TOKEN نامعتبر است (باید حداقل یک ':' داشته باشد)!\n"
            f"   → مقدار فعلی: {Config.BOT_TOKEN[:10]}...\n"
            "   → توکن کامل از @BotFather کپی کن"
        )
    elif len(Config.BOT_TOKEN.split(":")[1]) < 30:
        errors.append(
            "❌ BOT_TOKEN ناقص است (بخش بعد از ':' کمتر از ۳۰ کاراکتر)!\n"
            "   → توکن کامل از @BotFather کپی کن\n"
            "   → توکن باید شکل: 123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
        )
    
    if Config.ADMIN_ID == 0:
        errors.append(
            "❌ ADMIN_ID تنظیم نشده یا صفر است!\n"
            "   → آیدی عددی خودت را از @userinfobot بگیر\n"
            "   → در Render: Environment → ADMIN_ID"
        )
    elif Config.ADMIN_ID < 10000:
        errors.append(
            f"❌ ADMIN_ID نامعتبر است: {Config.ADMIN_ID}\n"
            "   → آیدی عددی تلگرام معمولاً ۹-۱۰ رقم است\n"
            "   → از @userinfobot دوباره بگیر"
        )
    
    if errors:
        print("=" * 70)
        print("🚨 خطا در تنظیمات ربات:")
        print("=" * 70)
        for err in errors:
            print(err)
            print("-" * 70)
        print("🔍 مقادیر فعلی Environment:")
        print(f"   BOT_TOKEN   = {Config.BOT_TOKEN[:15] + '...' if Config.BOT_TOKEN and len(Config.BOT_TOKEN) > 15 else Config.BOT_TOKEN}")
        print(f"   ADMIN_ID    = {Config.ADMIN_ID}")
        print(f"   BOT_USERNAME= {Config.BOT_USERNAME}")
        print(f"   ADS_CHANNEL = {Config.ADS_CHANNEL}")
        print(f"   GIFT_CHANNEL= {Config.GIFT_CHANNEL}")
        print("=" * 70)
        raise SystemExit(1)
    
    print("=" * 70)
    print("✅ تنظیمات با موفقیت بارگذاری شد")
    print(f"   🤖 Bot: @{Config.BOT_USERNAME}")
    print(f"   👤 Admin ID: {Config.ADMIN_ID}")
    print(f"   📢 Ads Channel: {Config.ADS_CHANNEL or '(تنظیم نشده)'}")
    print(f"   🎁 Gift Channel: {Config.GIFT_CHANNEL or '(تنظیم نشده)'}")
    print("=" * 70)


# اجرای بررسی در همان لحظه import
_validate_config()
