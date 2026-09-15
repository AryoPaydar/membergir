import re
from datetime import datetime, timedelta
import jdatetime

def is_valid_username(text: str) -> bool:
    """چک کردن آیدی کانال"""
    if not text:
        return False
    text = text.strip().replace("@", "")
    return bool(re.match(r"^[a-zA-Z0-9_]{5,32}$", text))

def is_valid_phone(phone: str) -> bool:
    """چک کردن شماره موبایل ایران"""
    return bool(re.match(r"^98\d{10}$", str(phone)))

def is_positive_int(text: str) -> bool:
    """چک کردن عدد صحیح مثبت"""
    return bool(re.match(r"^[0-9]+$", str(text).strip()))

def normalize_channel(text: str) -> str:
    """نرمالسازی آیدی کانال"""
    if not text:
        return ""
    text = text.strip().lower()
    for prefix in ("https://", "http://", "t.me/", "telegram.me/", "@"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip("/").split("/")[0]

def now_ts() -> int:
    return int(datetime.now().timestamp())

def jalali_now():
    """تاریخ و ساعت شمسی"""
    now = jdatetime.datetime.now()
    return now.strftime("%Y/%m/%d"), now.strftime("%H:%M:%S")

def jalali_full():
    """تاریخ کامل شمسی"""
    now = jdatetime.datetime.now()
    return now.strftime("%A %d %B %Y - %H:%M")

def format_number(n) -> str:
    """عدد با کاما"""
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return "0"

def parse_state_data(data: str):
    """تبدیل state_data به دیکشنری"""
    if not data:
        return {}
    import json
    try:
        return json.loads(data)
    except Exception:
        return {}

def dump_state_data(data: dict) -> str:
    import json
    return json.dumps(data, ensure_ascii=False)