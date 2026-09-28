from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# ==================== کیبورد اصلی کاربر ====================
def main_menu(is_admin=False):
    rows = [
        ["👤 حساب کاربری", "💰 دریافت سکه"],
        ["🚀 ثبت سفارش", "📋 پیگیری سفارش"],
        ["👥 زیرمجموعه‌گیری", "🎁 کد هدیه", "🏦 بانک انتقال"],
        ["🛍 فروشگاه", "🚀 ارتقا پنل", "🏆 برترین‌ها"],
        ["💡راهنما", "⚖️ قوانین", "💞حمایت مالی"],
        ["📨 ارتباط با مدیریت"],
    ]
    if is_admin:
        rows.append(["👑 پنل مدیریت"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def back_button():
    return ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)


def gift_user_back_keyboard():
    return ReplyKeyboardMarkup([["🔙 انصراف"]], resize_keyboard=True)


def rules_back_keyboard():
    return ReplyKeyboardMarkup([["🔙 بازگشت به صفحه اصلی"]], resize_keyboard=True)


def support_cancel_keyboard():
    return ReplyKeyboardMarkup([["🔙 انصراف"]], resize_keyboard=True)


def admin_back_keyboard():
    """کیبورد بازگشت به پنل مدیریت (برای زیرمنوهای ادمین)"""
    return ReplyKeyboardMarkup(
        [["🔙 بازگشت به پنل مدیریت"]],
        resize_keyboard=True
    )


def bank_menu():
    return ReplyKeyboardMarkup([
        ["💎 انتقال الماس"],
        ["📥 تاریخچه دریافت", "📤 تاریخچه انتقال"],
        ["🔙 بازگشت به منوی اصلی"],
    ], resize_keyboard=True)


# ==================== کیبورد پنل ادمین ====================
def admin_panel():
    return ReplyKeyboardMarkup([
        ["📈 آمار ربات", "📨 ارسال پیام", "🎗 تکمیل سفارش"],
        ["👥 مدیریت کاربران", "👤 ادمین‌ها", "🆔 تنظیم کانال"],
        ["🔮 جستجوگر", "🎉 کد هدیه", "📌 تنظیم سفارش"],
        ["♻️ پنل‌ها", "🏦 مبادلات سکه", "⚙️ زیرمجموعه‌گیری"],
        ["📇 تنظیم متن", "💳 تنظیمات انتقال", "✂️ تنظیمات لغو"],
        ["🔕 خاموش/روشن", "⚠️ اخطاردهی", "🔙 بازگشت به منو"],
    ], resize_keyboard=True)


# ==================== دکمه‌های شیشه‌ای ====================
def inline(rows):
    keyboard = []
    for row in rows:
        line = []
        for btn in row:
            if isinstance(btn, dict):
                line.append(InlineKeyboardButton(**btn))
            else:
                text, data = btn
                if data.startswith("http"):
                    line.append(InlineKeyboardButton(text, url=data))
                else:
                    line.append(InlineKeyboardButton(text, callback_data=data))
        keyboard.append(line)
    return InlineKeyboardMarkup(keyboard)


def confirm_cancel(order_id):
    return inline([
        [("✅ بله", f"cancel_confirm:{order_id}"), ("❌ خیر", "back")]
    ])
