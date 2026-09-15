from config import Config

def start_text(first_name, user_id):
    return (
        f"👋 سلام <b>{first_name}</b> عزیز\n\n"
        f"🆔 آیدی شما: <code>{user_id}</code>\n\n"
        f"به ربات خوش آمدید. از منوی زیر گزینه مورد نظر را انتخاب کنید."
    )

def account_text(user: dict):
    panel_info = Config.PANELS.get(user["panel"], {})
    return (
        f"👤 <b>حساب کاربری</b>\n\n"
        f"🆔 آیدی: <code>{user['user_id']}</code>\n"
        f"📆 تاریخ عضویت: {user['join_date']}\n"
        f"🎖 پنل: {user['panel']}\n"
        f"💰 موجودی: {user['coins']:,} سکه\n"
        f"⚠️ اخطار: {user['warnings']} از {Config.MAX_WARNINGS}\n"
        f"📌 سفارشات: {user['orders_count']}\n"
        f"🔗 تعداد عضویت: {user['ads_joined']}\n"
        f"👥 تعداد زیرمجموعه: {get_referral_count(user['user_id'])}\n"
        f"📥 دریافتی: {user['received_coins']:,}\n"
        f"📤 ارسالی: {user['sent_coins']:,}\n"
    )

def get_referral_count(user_id):
    """در handler اصلی پر می‌شود"""
    from database import db
    with db.conn() as c:
        r = c.execute(
            "SELECT COUNT(*) as c FROM users WHERE referrer_id = ?",
            (user_id,)
        ).fetchone()
        return r["c"] if r else 0