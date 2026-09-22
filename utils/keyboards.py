from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# ==================== کیبورد اصلی کاربر ====================
def main_menu(is_admin=False):
    rows = [
        ["💰 دریافت سکه", "👤 حساب کاربری"],
        ["🚀 ثبت سفارش", "👥 زیرمجموعه‌گیری"],
        ["🎁 کد هدیه", "🛍 فروشگاه"],
        ["🚀 ارتقا پنل", "🏆 برترین‌ها"],
        ["📋 پیگیری سفارش", "🏦 بانک انتقال"],
        ["⚖️ قوانین", "💡راهنما"],
        ["📨 ارتباط با مدیریت", "💞حمایت مالی"],
    ]
    if is_admin:
        rows.append(["👑 پنل مدیریت"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def back_button():
    return ReplyKeyboardMarkup([["🔙 بازگشت"]], resize_keyboard=True)

def gift_user_back_keyboard():
    return ReplyKeyboardMarkup([["🔙 انصراف"]], resize_keyboard=True)

# ==================== کیبورد بازگشت از قوانین ====================
def rules_back_keyboard():
    return ReplyKeyboardMarkup([["🔙 بازگشت به صفحه اصلی"]], resize_keyboard=True)

# ==================== کیبورد بانک انتقال ====================
def bank_menu():
    return ReplyKeyboardMarkup([
        ["💎 انتقال الماس"],
        ["📥 تاریخچه دریافت", "📤 تاریخچه انتقال"],
        ["🔙 بازگشت به منوی اصلی"],
    ], resize_keyboard=True)

# ==================== کیبورد پنل ادمین ====================
def admin_panel():
    return ReplyKeyboardMarkup([
        ["📈 آمار ربات", "📨 ارسال پیام"],
        ["🎉 کد هدیه", "🏦 مبادلات سکه"],
        ["📌 تنظیم سفارش", "♻️ پنل‌ها"],
        ["👤 ادمین‌ها", "🆔 آیدی‌یاب"],
        ["📇 تنظیم متن", "🆔 تنظیم کانال"],
        ["⚠️ اخطاردهی", "⚙️ زیرمجموعه‌گیری"],
        ["🎗 تکمیل سفارش", "🛐 پیگیری کاربر"],
        ["✂️ تنظیمات لغو", "💳 تنظیمات انتقال"],
        ["🔕 خاموش/روشن", "🔙 بازگشت به منو"],
    ], resize_keyboard=True)

# ==================== دکمه‌های شیشه‌ای ====================
def inline(rows):
    """rows = لیستی از لیست (text, callback_data) یا (text, url)"""
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
