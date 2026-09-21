from telegram import Update
from telegram.ext import ContextTypes
from database import db
from bot_manager import (
    get_user, update_user, transfer_coins,
    set_user_state, get_user_state,
    add_coins, remove_coins, is_admin, get_setting
)
from utils.keyboards import inline, main_menu, back_button, bank_menu
from utils.helpers import is_positive_int, now_ts, jalali_now


# ==================== منوی بانک ====================
async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی بانک انتقال"""
    user_id = update.effective_user.id
    set_user_state(user_id, "none")
    
    text = (
        "به بخش انتقال الماس خوش آمدید🌹\n"
        "\n"
        "در این بخش گزارشی از انتقالات الماس ها ارائه میگردد\n"
        "\n"
        "💎 با دکمه انتقال الماس می توانید الماس های خود را به دیگران انتقال دهید.\n"
        "\n"
        "📥 با دکمه تاریخچه دریافت‌ها می توانید کلیه مشخصات دریافت الماس های خود را مشاهده نمایید.\n"
        "\n"
        "📤 با دکمه تاریخچه انتقال‌ها می توانید کلیه مشخصات انتقال الماس های خود را مشاهده نمایید."
    )
    
    await update.message.reply_text(
        text,
        reply_markup=bank_menu()
    )


# ==================== انتقال الماس - مرحله ۱: شماره کاربری ====================
async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع انتقال الماس"""
    user_id = update.effective_user.id
    
    if not get_setting("transfer_enabled", "on") == "on":
        await update.message.reply_text("❌ انتقال الماس غیرفعال است.", reply_markup=main_menu(is_admin(user_id)))
        return
    
    set_user_state(user_id, "transfer_target")
    await update.message.reply_text(
        "🫆 شماره کاربری فرد مورد نظر که قصد انتقال الماس به آن را دارید وارد کنید\n"
        "\n"
        "⚠️ شماره کاربری هر شخص در قسمت حساب کاربری قابل دریافت است",
        reply_markup=back_button()
    )


# ==================== تاریخچه دریافت ====================
async def history_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تاریخچه دریافت‌ها"""
    user_id = update.effective_user.id
    set_user_state(user_id, "none")
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT from_id, amount, created_at
            FROM transactions
            WHERE to_id = ? AND type = 'transfer'
            ORDER BY id DESC LIMIT 50
        """, (user_id,)).fetchall()
    
    if not rows:
        await update.message.reply_text(
            "تاریخچه ای وجود ندارد\n"
            "تاریخچه انتقال هرشب ساعت ۲۴ ریست میشود",
            reply_markup=bank_menu()
        )
        return
    
    text = "تاریخچه دریافت :\n\n"
    for r in rows:
        text += (
            f"از : {r['from_id']}\n"
            f"مقدار : {r['amount']:,} الماس\n"
            f"-----------\n"
        )
    
    await update.message.reply_text(text, reply_markup=bank_menu())


# ==================== تاریخچه انتقال ====================
async def history_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تاریخچه انتقال‌ها"""
    user_id = update.effective_user.id
    set_user_state(user_id, "none")
    
    with db.conn() as c:
        rows = c.execute("""
            SELECT to_id, amount, created_at
            FROM transactions
            WHERE from_id = ? AND type = 'transfer'
            ORDER BY id DESC LIMIT 50
        """, (user_id,)).fetchall()
    
    if not rows:
        await update.message.reply_text(
            "تاریخچه ای وجود ندارد\n"
            "تاریخچه انتقال هرشب ساعت ۲۴ ریست میشود",
            reply_markup=bank_menu()
        )
        return
    
    text = "تاریخچه انتقال:\n\n"
    for r in rows:
        text += (
            f"به : {r['to_id']}\n"
            f"مقدار : {r['amount']:,} الماس\n"
            f"-----------\n"
        )
    
    await update.message.reply_text(text, reply_markup=bank_menu())


# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if not state or state == "none":
        return False
    
    # === بازگشت ===
    if text == "🔙 بازگشت به منوی اصلی":
        set_user_state(user_id, "none")
        await update.message.reply_text(
            "🏠 منوی اصلی",
            reply_markup=main_menu(is_admin(user_id))
        )
        return True
    
    # === انتقال الماس: دریافت شماره کاربری ===
    if state == "transfer_target":
        if not is_positive_int(text):
            await update.message.reply_text(
                "❌ کاربری با این شماره کاربری یافت نشده است. لطفا شماره صحیح را وارد نمایید.\n"
                "\n"
                "🫆 شماره کاربری هر شخص در قسمت حساب کاربری قابل دریافت است",
                reply_markup=back_button()
            )
            return True
        
        target_id = int(text)
        
        # چک خود کاربر
        if target_id == user_id:
            await update.message.reply_text(
                "❌ نمی‌توانید به خودتان انتقال دهید.",
                reply_markup=back_button()
            )
            return True
        
        target = get_user(target_id)
        if not target:
            await update.message.reply_text(
                "❌ کاربری با این شماره کاربری یافت نشده است. لطفا شماره صحیح را وارد نمایید.\n"
                "\n"
                "🫆 شماره کاربری هر شخص در قسمت حساب کاربری قابل دریافت است",
                reply_markup=back_button()
            )
            return True
        
        # چک موجودی کاربر
        user = get_user(user_id)
        coins = user.get("coins", 0) or 0
        
        min_transfer = int(get_setting("transfer_min", "10"))
        max_transfer = int(get_setting("transfer_max", "1000"))
        
        set_user_state(user_id, "transfer_amount", {"target_id": target_id})
        
        await update.message.reply_text(
            f"چه تعداد الماس میخواهید انتقال دهید؟\n"
            f"\n"
            f"🪫 حداقل مقدار مجاز انتقال : {min_transfer:,} الماس\n"
            f"🔋 حداکثر مقدار مجاز انتقال : {max_transfer:,}\n"
            f"💰 موجودی شما : {coins:,}",
            reply_markup=back_button()
        )
        return True
    
    # === انتقال الماس: دریافت مقدار ===
    if state == "transfer_amount":
        if not is_positive_int(text):
            await update.message.reply_text(
                "❌ فقط عدد مجاز است.",
                reply_markup=back_button()
            )
            return True
        
        amount = int(text)
        target_id = data.get("target_id")
        
        min_transfer = int(get_setting("transfer_min", "10"))
        max_transfer = int(get_setting("transfer_max", "1000"))
        
        # چک حداقل
        if amount < min_transfer:
            await update.message.reply_text(
                f"⚠️ حداقل مقدار مجاز انتقال رعایت نشده است.\n"
                f"🪫 حداقل مقدار مجاز انتقال : {min_transfer:,} الماس",
                reply_markup=back_button()
            )
            return True
        
        # چک حداکثر
        if amount > max_transfer:
            await update.message.reply_text(
                f"⚠️ حداکثر مقدار مجاز انتقال رعایت نشده است.\n"
                f"🔋 حداکثر مقدار مجاز انتقال : {max_transfer:,} الماس",
                reply_markup=back_button()
            )
            return True
        
        # چک موجودی
        user = get_user(user_id)
        if (user.get("coins", 0) or 0) < amount:
            await update.message.reply_text(
                "❌ موجودی شما کافی نیست.",
                reply_markup=back_button()
            )
            return True
        
        target = get_user(target_id)
        target_name = target.get("first_name") if target else "کاربر"
        
        set_user_state(user_id, "transfer_confirm", {
            "target_id": target_id,
            "amount": amount
        })
        
        await update.message.reply_text(
            f"آیا از انتقال الماس به {target_name} مطمئن هستید ؟\n\n"
            f"💰 مقدار : {amount:,} الماس\n"
            f"🫆 شماره کاربری مقصد : {target_id}",
            reply_markup=inline([
                [("✅ بله", "transfer_yes"), ("❌ خیر", "transfer_no")],
            ])
        )
        return True
    
    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    user_id = q.from_user.id
    
    if data == "transfer_yes":
        await q.answer()
        state, sdata = get_user_state(user_id)
        if state != "transfer_confirm":
            return True
        
        target_id = sdata.get("target_id")
        amount = sdata.get("amount")
        
        # انتقال اتمیک
        success = transfer_coins(user_id, target_id, amount)
        
        set_user_state(user_id, "none")
        
        if success:
            target = get_user(target_id)
            target_name = target.get("first_name") if target else "کاربر"
            
            await q.message.edit_text(
                f"✅ انتقال با موفقیت انجام شد.\n\n"
                f"💰 مقدار : {amount:,} الماس\n"
                f"👤 به : {target_name} ({target_id})"
            )
            
            # اطلاع به کاربر مقصد
            try:
                sender = get_user(user_id)
                sender_name = sender.get("first_name") if sender else "کاربر"
                await context.bot.send_message(
                    target_id,
                    f"🎉 تبریک!\n\n"
                    f"شما {amount:,} الماس از {sender_name} دریافت کردید."
                )
            except Exception:
                pass
            
            # گزارش به ادمین
            if get_setting("transfer_report", "on") == "on":
                try:
                    from config import Config
                    await context.bot.send_message(
                        Config.ADMIN_ID,
                        f"💳 انتقال الماس\n\n"
                        f"👤 از : {user_id}\n"
                        f"👤 به : {target_id}\n"
                        f"💰 مقدار : {amount:,}"
                    )
                except Exception:
                    pass
            
            # دکمه منوی اصلی
            await context.bot.send_message(
                user_id,
                "🏠 منوی اصلی",
                reply_markup=main_menu(is_admin(user_id))
            )
        else:
            await q.message.edit_text(
                "❌ انتقال انجام نشد. موجودی کافی نیست."
            )
            await context.bot.send_message(
                user_id,
                "🏠 منوی اصلی",
                reply_markup=main_menu(is_admin(user_id))
            )
        return True
    
    if data == "transfer_no":
        await q.answer("لغو شد.")
        set_user_state(user_id, "none")
        try:
            await q.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            user_id,
            "🏠 منوی اصلی",
            reply_markup=main_menu(is_admin(user_id))
        )
        return True
    
    return False
