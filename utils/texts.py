from config import Config

def start_text(first_name, user_id):
    from bot_manager import get_setting
    default = (
        f"👋 سلام <b>{first_name}</b> عزیز\n\n"
        f"🆔 آیدی شما: <code>{user_id}</code>\n\n"
        f"به ربات خوش آمدید. از منوی زیر گزینه مورد نظر را انتخاب کنید."
    )
    text = get_setting("start_text", default)
    # جایگزینی متغیرها
    text = text.replace("{first_name}", first_name or "")
    text = text.replace("{user_id}", str(user_id))
    return text


def account_text(user: dict):
    from database import db
    from utils.helpers import jalali_now, now_ts
    import jdatetime
    from datetime import datetime
    
    first_name = user.get("first_name") or "کاربر"
    username = user.get("username")
    username_display = f"@{username}" if username else "ندارد"
    user_id = user["user_id"]
    
    try:
        dt = datetime.strptime(str(user["join_date"])[:19], "%Y-%m-%d %H:%M:%S")
        join_date_jalali = jdatetime.date.fromgregorian(date=dt.date()).strftime("%Y/%m/%d")
    except Exception:
        join_date_jalali = str(user.get("join_date", ""))[:10]
    
    panel = user.get("panel", "عادی")
    is_verified = bool(user.get("phone"))
    verify_status = "تایید شده ✅" if is_verified else "تایید نشده ❌"
    warnings = user.get("warnings", 0)
    max_warn = Config.MAX_WARNINGS
    
    today, _ = jalali_now()
    today_earned = user.get("today_earned", 0) if user.get("today_date") == today else 0
    total_earned = user.get("total_earned", 0)
    total_spent = user.get("total_spent", 0)
    
    with db.conn() as c:
        gift_row = c.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE to_id = ? AND type = 'admin_gift'
        """, (user_id,)).fetchone()
        admin_gift = gift_row["total"] if gift_row else 0
        
        ref_total = c.execute(
            "SELECT COUNT(*) c FROM users WHERE referrer_id = ?", (user_id,)
        ).fetchone()["c"]
        
        today_jalali = today
        ref_today = 0
        refs = c.execute(
            "SELECT join_date FROM users WHERE referrer_id = ?", (user_id,)
        ).fetchall()
        for r in refs:
            try:
                dt2 = datetime.strptime(str(r["join_date"])[:19], "%Y-%m-%d %H:%M:%S")
                jd = jdatetime.date.fromgregorian(date=dt2.date()).strftime("%Y/%m/%d")
                if jd == today_jalali:
                    ref_today += 1
            except Exception:
                pass
        
        ref_verified = c.execute("""
            SELECT COUNT(*) c FROM users
            WHERE referrer_id = ? AND ads_joined >= 3
        """, (user_id,)).fetchone()["c"]
        
        commission_row = c.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE to_id = ? AND type IN ('referral', 'referral_commission')
        """, (user_id,)).fetchone()
        inv_commission = commission_row["total"] if commission_row else 0
    
    hourly_earned = user.get("hourly_earned", 0)
    last_hourly = user.get("last_hourly", 0)
    now = now_ts()
    cooldown = Config.HOURLY_GIFT_COOLDOWN
    next_hourly = last_hourly + cooldown
    if now < next_hourly:
        remaining = next_hourly - now
        minutes = remaining // 60
        seconds = remaining % 60
        time_left = f"{minutes} دقیقه و {seconds} ثانیه"
    else:
        time_left = "آماده دریافت ✅"
    
    coins = user.get("coins", 0)
    
    text = (
        f"🔰 نام کاربری : <b>{first_name}</b>\n"
        f"🆔 یوزرنیم : {username_display}\n"
        f"🫆 شماره کاربری : <code>{user_id}</code>\n"
        f"📆 تاریخ عضویت : {join_date_jalali}\n"
        f"🏵 نوع پنل : {panel}\n"
        f"💎 حساب کاربری : {verify_status}\n"
        f"⚠️ اخطار : {warnings} از {max_warn}\n"
        f"\n"
        f"📊 مجموع موجودی کسب شده : {total_earned:,}\n"
        f"📈 موجودی کسب شده در امروز : {today_earned:,}\n"
        f"📉 مجموع موجودی مصرفی : {total_spent:,}\n"
        f"🎁 هدیه مدیریت : {admin_gift:,}\n"
        f"🎊 هدیه ساعتی : {hourly_earned:,}\n"
        f"⏳ زمان باقی مانده هدیه ساعتی : {time_left}\n"
        f"\n"
        f"💳 <b>انتقالات</b>\n"
        f"📥 دریافتی : {user.get('received_coins', 0):,}\n"
        f"📤 واریزی : {user.get('sent_coins', 0):,}\n"
        f"\n"
        f"👥 <b>زیر مجموعه ها</b>\n"
        f"⚜️ مجموع : {ref_total:,}\n"
        f"🔆 امروز : {ref_today:,}\n"
        f"💯 زیرمجموعه تایید شده : {ref_verified:,}\n"
        f"💳 پورسانت دریافتی : {inv_commission:,}\n"
        f"\n"
        f"💰 موجودی : <b>{coins:,}</b>"
    )
    
    return text


def get_referral_count(user_id):
    from database import db
    with db.conn() as c:
        r = c.execute(
            "SELECT COUNT(*) as c FROM users WHERE referrer_id = ?",
            (user_id,)
        ).fetchone()
        return r["c"] if r else 0
