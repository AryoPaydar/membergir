from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    is_admin, set_user_state, get_user_state,
    get_user, add_coins
)
from utils.keyboards import inline, admin_panel, admin_back_keyboard
from utils.helpers import is_positive_int


# ==================== منوی تکمیل سفارش ====================
async def complete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    set_user_state(update.effective_user.id, "none")

    await update.message.reply_text(
        "✅ با استفاده از تنظیمات این بخش می توانید به سفارشات موجود در کانال تبلیغات پایان بدهید\n\n"
        "گزینه مورد نظر خود را انتخاب کنید :",
        reply_markup=inline([
            [("✅ تکمیل بدون الماس", "acomplete_free"),
             ("💎 تکمیل با الماس", "acomplete_refund")],
            [("🔙 بازگشت به پنل مدیریت", "acomplete_back")],
        ])
    )


async def acomplete_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


# ==================== شروع تکمیل (بدون الماس) ====================
async def complete_free_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "acomplete_input", {"mode": "free"})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "کد پیگیری پست یا پست هایی که میخواهید تکمیل شود را وارد نمایید :\n"
        "مثلا 80 - 85",
        reply_markup=admin_back_keyboard()
    )


# ==================== شروع تکمیل (با الماس) ====================
async def complete_refund_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "acomplete_input", {"mode": "refund"})
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        q.from_user.id,
        "کد پیگیری پست یا پست هایی که میخواهید تکمیل شود را وارد نمایید :\n"
        "مثلا 80 - 85",
        reply_markup=admin_back_keyboard()
    )


# ==================== تجزیه ورودی ====================
def _parse_post_ids(text: str):
    """
    ورودی: "80" یا "80 - 85" یا "80-85" یا "80 ، 85"
    خروجی: لیست شماره پست‌ها یا None
    """
    text = text.strip().replace("–", "-").replace("—", "-")

    # حالت 1: یک عدد
    if text.isdigit():
        return [int(text)]

    # حالت 2: بازه "80 - 85"
    if "-" in text:
        parts = [p.strip() for p in text.split("-") if p.strip()]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            a, b = int(parts[0]), int(parts[1])
            if a > b:
                a, b = b, a
            return list(range(a, b + 1))

    return None


# ==================== پردازش تکمیل ====================
async def _process_complete(update, context, text):
    user_id = update.effective_user.id
    state, data = get_user_state(user_id)
    mode = data.get("mode", "free")

    ids = _parse_post_ids(text)

    if not ids:
        await update.message.reply_text(
            "❌ فرمت ورودی نامعتبر.\n\nمثال صحیح: 80 یا 80 - 85",
            reply_markup=admin_back_keyboard()
        )
        return

    # چک اینکه پست‌ها وجود دارن
    with db.conn() as c:
        placeholders = ",".join("?" * len(ids))
        rows = c.execute(
            f"SELECT id, post_id, admin_id, channel, member_target, member_received, coins_cost "
            f"FROM orders WHERE post_id IN ({placeholders}) AND status = 'running'",
            ids
        ).fetchall()

    if not rows:
        await update.message.reply_text(
            "❌ هیچ سفارش فعالی با این کد(ها) یافت نشد.",
            reply_markup=admin_back_keyboard()
        )
        return

    found_post_ids = [r["post_id"] for r in rows]
    missing = [i for i in ids if i not in found_post_ids]

    # ذخیره در state برای تأیید
    set_user_state(user_id, "acomplete_confirm", {
        "mode": mode,
        "post_ids": found_post_ids,
    })

    if len(found_post_ids) == 1:
        title = f"پست {found_post_ids[0]}"
    else:
        title = f"پست های {found_post_ids[0]} تا {found_post_ids[-1]}"

    extra = ""
    if missing:
        extra = f"\n\n⚠️ پست های {', '.join(str(m) for m in missing)} یافت نشدند و نادیده گرفته میشن."

    await update.message.reply_text(
        f"آیا از تکمیل {title} مطمئن هستید ؟{extra}",
        reply_markup=inline([
            [("✅ بله", "acomplete_yes"), ("❌ خیر", "acomplete_back")]
        ])
    )


# ==================== تأیید و اجرا ====================
async def acomplete_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    state, data = get_user_state(user_id)
    if state != "acomplete_confirm":
        await q.message.reply_text("❌ اطلاعات منقضی شده.")
        return

    mode = data.get("mode", "free")
    post_ids = data.get("post_ids", [])

    if not post_ids:
        set_user_state(user_id, "none")
        await q.message.reply_text("❌ لیست خالی است.")
        return

    try:
        await q.message.delete()
    except Exception:
        pass

    set_user_state(user_id, "none")

    success_count = 0
    fail_count = 0

    for pid in post_ids:
        with db.conn() as c:
            o = c.execute(
                "SELECT * FROM orders WHERE post_id = ? AND status = 'running'",
                (pid,)
            ).fetchone()

        if not o:
            fail_count += 1
            continue

        o = dict(o)
        order_admin = o["admin_id"]
        channel = o["channel"]
        remaining = o["member_target"] - o["member_received"]
        coins_cost = o["coins_cost"]
        member_target = o["member_target"]

        # محاسبه الماس برگشتی: نسبت اعضای دریافت‌نشده به کل * هزینه
        if mode == "refund":
            if member_target > 0:
                refund = int((remaining / member_target) * coins_cost)
            else:
                refund = 0
        else:
            refund = 0

        # آپدیت سفارش
        with db.conn() as c:
            c.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (o["id"],))

        # حذف پست از کانال
        try:
            await context.bot.delete_message(f"@{Config.ADS_CHANNEL}", pid)
        except Exception:
            pass

        # پیام به سفارش‌دهنده
        try:
            if mode == "refund":
                msg = (
                    f"☣️ سفارش ممبرگیری برای کانال @{channel} با کد پیگیری {pid} "
                    f"به دلیل تکمیل نشدن در زمان طولانی کنسل گردید و مقدار {refund:,} الماس به حساب شما افزوده شد.\n\n"
                    f"✅ برای تکمیل سریعتر پیشنهاد میشود که سفارش خود را دوباره ارسال فرمایید."
                )
                if refund > 0:
                    add_coins(order_admin, refund, "order_cancel_refund",
                              f"بازگشت از سفارش #{pid}")
            else:
                msg = (
                    f"💯 سفارش ممبرگیری برای کانال @{channel} با کد پیگیری {pid} به پایان رسید."
                )

            await context.bot.send_message(order_admin, msg)
        except Exception:
            pass

        success_count += 1

    # گزارش نهایی به ادمین
    mode_text = "بدون الماس" if mode == "free" else "با الماس"
    report = (
        f"✅ تکمیل {mode_text} انجام شد.\n\n"
        f"✔️ موفق: {success_count}\n"
        f"❌ ناموفق: {fail_count}"
    )

    await context.bot.send_message(user_id, report, reply_markup=admin_panel())


# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False

    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()

    if not state or state == "none":
        return False

    if text == "🔙 بازگشت به پنل مدیریت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True

    if state == "acomplete_input":
        await _process_complete(update, context, text)
        return True

    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False

    if data == "acomplete_free":
        await complete_free_start(update, context)
        return True
    if data == "acomplete_refund":
        await complete_refund_start(update, context)
        return True
    if data == "acomplete_back":
        await acomplete_back(update, context)
        return True
    if data == "acomplete_yes":
        await acomplete_yes(update, context)
        return True

    return False
