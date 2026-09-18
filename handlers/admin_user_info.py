from telegram import Update
from telegram.ext import ContextTypes
from database import db
from bot_manager import is_admin, set_user_state, get_user_state, get_user
from utils.keyboards import back_button, admin_panel
from utils.helpers import is_positive_int


async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "admin_user_info")
    await update.message.reply_text(
        "✅ با استفاده از این بخش می توانید اطلاعات حساب کاربری کاربر مورد نظر را دریافت کنید\n\n"
        "👈آیدی عددی کاربر مورد نظر را ارسال نمایید",
        reply_markup=back_button()
    )


async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if state != "admin_user_info":
        return False
    
    if text == "🔙 بازگشت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True
    
    if not is_positive_int(text):
        await update.message.reply_text("❌ فقط آیدی عددی مجاز است.")
        return True
    
    target = get_user(int(text))
    if not target:
        await update.message.reply_text("⚠️ این کاربر در دیتابیس ربات شما یافت نشد.")
        set_user_state(user_id, "none")
        return True
    
    # آمار زیرمجموعه
    with db.conn() as c:
        ref_count = c.execute(
            "SELECT COUNT(*) c FROM users WHERE referrer_id = ?",
            (target["user_id"],)
        ).fetchone()["c"]
        
        admin_gift = c.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE to_id = ? AND type = 'admin_gift'
        """, (target["user_id"],)).fetchone()["total"]
        
        commission = c.execute("""
            SELECT COALESCE(SUM(amount), 0) as total FROM transactions
            WHERE to_id = ? AND type IN ('referral', 'referral_commission')
        """, (target["user_id"],)).fetchone()["total"]
    
    text_out = (
        f"🔰 شماره کاربری : <code>{target['user_id']}</code>\n"
        f"🗣 نام کاربری : {target.get('first_name') or 'ندارد'}\n"
        f"🆔 یوزرنیم : @{target.get('username') or 'ندارد'}\n"
        f"📆 تاریخ عضویت : {str(target.get('join_date', ''))[:10]}\n"
        f"♻️ نوع پنل : {target.get('panel', 'عادی')}\n"
        f"\n"
        f"⚠️ اخطار : {target.get('warnings', 0)} از 3\n"
        f"🎁 هدیه مدیریت : {admin_gift:,}\n"
        f"\n"
        f"💳 انتقالات\n"
        f"📥 دریافتی : {target.get('received_coins', 0):,}\n"
        f"📤 واریزی : {target.get('sent_coins', 0):,}\n"
        f"\n"
        f"👥 زیر مجموعه ها\n"
        f"✔️ مجموع : {ref_count:,}\n"
        f"✔️ پورسانت دریافتی : {commission:,}\n"
        f"\n"
        f"✅ موجودی : {target.get('coins', 0):,}"
    )
    
    set_user_state(user_id, "none")
    await update.message.reply_text(
        text_out,
        parse_mode="HTML",
        reply_markup=admin_panel()
    )
    return True
