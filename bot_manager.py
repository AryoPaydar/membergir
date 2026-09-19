from telegram import Update
from telegram.ext import ContextTypes
from database import db
from config import Config
from utils.helpers import now_ts

# ==================== کاربر ====================
def get_user(user_id: int):
    with db.conn() as c:
        r = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(r) if r else None

def create_user(user_id: int, first_name: str = "", username: str = "", referrer_id: int = None):
    from utils.helpers import jalali_now
    today, _ = jalali_now()
    with db.conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO users (user_id, first_name, username, coins, referrer_id, today_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, first_name, username, Config.DEFAULT_COINS, referrer_id, today))
        return get_user(user_id)

def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    with db.conn() as c:
        c.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)

def set_user_state(user_id: int, state: str, data: dict = None):
    import json
    update_user(user_id, state=state, state_data=json.dumps(data, ensure_ascii=False) if data else None)

def get_user_state(user_id: int):
    user = get_user(user_id)
    if not user:
        return None, {}
    import json
    data = {}
    if user.get("state_data"):
        try:
            data = json.loads(user["state_data"])
        except Exception:
            data = {}
    return user.get("state"), data

# ==================== سکه ====================
def add_coins(user_id: int, amount: int, tx_type: str = "add", desc: str = ""):
    """افزودن سکه به کاربر با ثبت تراکنش — اتمیک"""
    if amount == 0:
        return
    from utils.helpers import jalali_now
    today, _ = jalali_now()
    with db.conn() as c:
        row = c.execute("SELECT today_date FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row and row["today_date"] != today:
            c.execute(
                "UPDATE users SET today_earned = 0, referral_today = 0, today_date = ? WHERE user_id = ?",
                (today, user_id)
            )
        c.execute("""
            UPDATE users
            SET coins = coins + ?,
                total_earned = total_earned + ?,
                today_earned = today_earned + ?
            WHERE user_id = ?
        """, (amount, amount, amount, user_id))
        c.execute("""
            INSERT INTO transactions (to_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        """, (user_id, amount, tx_type, desc))

def remove_coins(user_id: int, amount: int, tx_type: str = "remove", desc: str = ""):
    """کسر سکه — با چک موجودی"""
    with db.conn() as c:
        row = c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row or row["coins"] < amount:
            return False
        c.execute("""
            UPDATE users
            SET coins = coins - ?,
                total_spent = total_spent + ?
            WHERE user_id = ?
        """, (amount, amount, user_id))
        c.execute("""
            INSERT INTO transactions (from_id, amount, type, description)
            VALUES (?, ?, ?, ?)
        """, (user_id, amount, tx_type, desc))
        return True

def transfer_coins(from_id: int, to_id: int, amount: int) -> bool:
    """انتقال اتمیک سکه بین دو کاربر"""
    if amount <= 0 or from_id == to_id:
        return False
    with db.conn() as c:
        row = c.execute("SELECT coins FROM users WHERE user_id = ?", (from_id,)).fetchone()
        if not row or row["coins"] < amount:
            return False
        c.execute("UPDATE users SET coins = coins - ?, sent_coins = sent_coins + ?, total_spent = total_spent + ? WHERE user_id = ?",
                  (amount, amount, amount, from_id))
        c.execute("UPDATE users SET coins = coins + ?, received_coins = received_coins + ?, total_earned = total_earned + ? WHERE user_id = ?",
                  (amount, amount, amount, to_id))
        c.execute("""
            INSERT INTO transactions (from_id, to_id, amount, type, description)
            VALUES (?, ?, ?, 'transfer', ?)
        """, (from_id, to_id, amount, f"انتقال از {from_id} به {to_id}"))
        return True

# ==================== ادمین ====================
def is_admin(user_id: int) -> bool:
    if user_id == Config.ADMIN_ID:
        return True
    with db.conn() as c:
        r = c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
        return r is not None

def is_main_admin(user_id: int) -> bool:
    return user_id == Config.ADMIN_ID

def add_admin(user_id: int, by: int):
    with db.conn() as c:
        c.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, by))

def remove_admin(user_id: int):
    if user_id == Config.ADMIN_ID:
        return False
    with db.conn() as c:
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    return True

def list_admins():
    with db.conn() as c:
        return [r["user_id"] for r in c.execute("SELECT user_id FROM admins").fetchall()]

# ==================== بن ====================
def ban_user(user_id: int) -> bool:
    with db.conn() as c:
        row = c.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return False
        c.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
        return True

def unban_user(user_id: int) -> bool:
    with db.conn() as c:
        row = c.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return False
        c.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
        return True

def is_banned(user_id: int) -> bool:
    with db.conn() as c:
        r = c.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return bool(r and r["banned"])

# ==================== اخطار ====================
def add_warning(user_id: int) -> int:
    with db.conn() as c:
        c.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id = ?", (user_id,))
        r = c.execute("SELECT warnings FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return r["warnings"] if r else 0

# ==================== تنظیمات ====================
def get_setting(key: str, default: str = None) -> str:
    with db.conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return r["value"] if r else default

def set_setting(key: str, value: str):
    with db.conn() as c:
        c.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))

# ==================== بررسی عضویت ====================
async def check_membership(context, channel: str, user_id: int) -> bool:
    if not channel:
        return True
    try:
        member = await context.bot.get_chat_member(f"@{channel}", user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def check_bot_admin(context, channel: str) -> bool:
    try:
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(f"@{channel}", me.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

# ==================== پنل (اصلاح‌شده) ====================
def get_panel_config(panel_name: str) -> dict:
    """
    تنظیمات پنل رو برمیگردونه.
    اول از settings (دیتابیس) میخونه، اگه نبود از Config.PANELS
    """
    # پیش‌فرض از Config
    default_cfg = Config.PANELS.get(panel_name, Config.PANELS["عادی"])
    result = dict(default_cfg)  # کپی
    
    # مپ پنل به کلید توی settings
    key_map = {
        "عادی":    "normal",
        "حرفه ای": "pro",
        "ویژه":    "vip",
    }
    prefix = key_map.get(panel_name, "normal")
    
    # خوندن از settings
    try:
        # سکه روزانه
        val = get_setting(f"panel_{prefix}_daily", None)
        if val is not None:
            result["daily"] = int(float(val))
        
        # سکه عضویت
        val = get_setting(f"panel_{prefix}_join_coin", None)
        if val is not None:
            result["join_coin"] = float(val)
        
        # سکه زیرمجموعه
        val = get_setting(f"panel_{prefix}_invite_coin", None)
        if val is not None:
            result["invite_coin"] = int(float(val))
    except Exception:
        pass
    
    return result

def get_daily_gift(user: dict) -> int:
    return get_panel_config(user["panel"])["daily"]

def get_join_coin(user: dict) -> int:
    return get_panel_config(user["panel"])["join_coin"]

def get_invite_coin(user: dict) -> int:
    return get_panel_config(user["panel"])["invite_coin"]

# ==================== بررسی قدرت ربات ====================
def is_bot_on() -> bool:
    return get_setting("bot_power", "on") == "on"

def set_bot_power(on: bool):
    set_setting("bot_power", "on" if on else "off")

# ==================== بررسی پاداش زیرمجموعه ====================
async def check_referral_milestone(context, user_id: int):
    user = get_user(user_id)
    if not user:
        return
    
    referrer_id = user.get("referrer_id")
    if not referrer_id:
        return
    
    if user.get("referral_rewarded"):
        return
    
    threshold = int(get_setting("referral_join_threshold", str(Config.REFERRAL_JOIN_THRESHOLD)))
    if user.get("ads_joined", 0) < threshold:
        return
    
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
    
    add_coins(
        referrer_id, invite_coin, "referral_commission",
        f"پاداش زیرمجموعه {user_id} بعد از {threshold} عضویت"
    )
    
    update_user(user_id, referral_rewarded=1)
    
    with db.conn() as c:
        c.execute(
            "UPDATE users SET referral_today = referral_today + 1 WHERE user_id = ?",
            (referrer_id,)
        )
    
    try:
        await context.bot.send_message(
            referrer_id,
            f"🎉تبریک!!\n"
            f"\n"
            f"🎁 دریافت {invite_coin} الماس هدیه \n"
            f"\n"
            f"👈یکی از زیرمجموعه های شما برای اولین بار {threshold} دریافت الماس (عضویت در کانال) انجام داد\n"
            f"\n"
            f"✅ {invite_coin} الماس بصورت هدیه به حساب شما اضافه شد\n"
            f"\n"
            f"👌همچنین محاسبه {commission_percent} درصد پورسانت حاصل از فعالیت کاربر برای شما فعال شد",
            parse_mode="HTML"
        )
    except Exception:
        pass
