from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import get_user, update_user, set_user_state, get_user_state, is_admin, get_panel_config
from utils.keyboards import inline, main_menu, back_button
from utils.helpers import format_number

async def panel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        return
    
    panel_name = user["panel"]
    panel_cfg = get_panel_config(panel_name)
    
    # آمار پنل فعلی
    text = (
        f"🚀 <b>پنل کاربری</b>\n\n"
        f"🎖 پنل فعلی: <b>{panel_name}</b>\n"
        f"💰 سکه روزانه: {panel_cfg['daily']}\n"
        f"👥 سکه به ازای هر عضویت: {panel_cfg['join_coin']}\n"
        f"🎁 سکه به ازای هر زیرمجموعه: {panel_cfg['invite_coin']}\n"
    )
    
    if user["panel_days"] > 0:
        text += f"⌛️ اعتبار پنل: {user['panel_days']} روز\n"
    else:
        text += f"⌛️ اعتبار پنل: نامحدود\n"
    
    text += f"\n👥 زیرمجموعه‌های شما: {user.get('referral_count', 0)}\n"
    
    # دکمه‌های ارتقا
    rows = []
    for p_name, p_cfg in Config.PANELS.items():
        if p_name == panel_name:
            continue
        # چک سطح بالاتر
        if not _is_upgrade(panel_name, p_name):
            continue
        
        cost = p_cfg["upgrade_cost"]
        can_afford = user["coins"] >= cost
        status = "✅" if can_afford else "❌"
        rows.append([
            (f"{status} ارتقا به {p_name} | {cost} سکه", f"panel_upgrade:{p_name}")
        ])
    
    rows.append([("🔙 بازگشت", "back")])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=inline(rows))

def _is_upgrade(current: str, target: str) -> bool:
    """چک می‌کند که آیا target ارتقا از current است"""
    order = ["عادی", "حرفه ای", "ویژه"]
    try:
        return order.index(target) > order.index(current)
    except ValueError:
        return False

async def upgrade_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    target_panel = q.data.split(":", 1)[1]
    
    user = get_user(user_id)
    if not user:
        await q.answer("❌ کاربر یافت نشد.", show_alert=True)
        return
    
    if target_panel not in Config.PANELS:
        await q.answer("❌ پنل نامعتبر.", show_alert=True)
        return
    
    if not _is_upgrade(user["panel"], target_panel):
        await q.answer("❌ نمی‌توانید به این پنل ارتقا دهید.", show_alert=True)
        return
    
    cost = Config.PANELS[target_panel]["upgrade_cost"]
    if user["coins"] < cost:
        await q.answer(f"❌ موجودی کافی نیست! ({cost} سکه لازم است)", show_alert=True)
        return
    
    # تأیید نهایی
    await q.answer()
    await q.message.reply_text(
        f"⁉️ آیا از ارتقا به پنل <b>{target_panel}</b> مطمئن هستید؟\n\n"
        f"💰 هزینه: {cost:,} سکه\n"
        f"💳 موجودی فعلی: {user['coins']:,} سکه\n"
        f"💳 موجودی بعد از ارتقا: {user['coins'] - cost:,} سکه",
        parse_mode="HTML",
        reply_markup=inline([
            [("✅ بله، ارتقا بده", f"panel_confirm:{target_panel}"),
             ("❌ خیر", "back")],
        ])
    )

async def confirm_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    target_panel = q.data.split(":", 1)[1]
    
    user = get_user(user_id)
    if not user or target_panel not in Config.PANELS:
        await q.answer("❌ خطا.", show_alert=True)
        return
    
    if not _is_upgrade(user["panel"], target_panel):
        await q.answer("❌ خطا.", show_alert=True)
        return
    
    cost = Config.PANELS[target_panel]["upgrade_cost"]
    
    # کسر اتمیک سکه + تغییر پنل
    with db.conn() as c:
        row = c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row or row["coins"] < cost:
            await q.answer("❌ موجودی کافی نیست.", show_alert=True)
            return
        c.execute(
            "UPDATE users SET coins = coins - ?, panel = ? WHERE user_id = ?",
            (cost, target_panel, user_id)
        )
        c.execute("""
            INSERT INTO transactions (from_id, amount, type, description)
            VALUES (?, ?, 'panel_upgrade', ?)
        """, (user_id, cost, f"ارتقا به {target_panel}"))
    
    await q.answer("✅ ارتقا انجام شد.", show_alert=True)
    try:
        await q.message.delete()
    except Exception:
        pass
    
    new_user = get_user(user_id)
    await context.bot.send_message(
        user_id,
        f"🎉 تبریک! پنل شما به <b>{target_panel}</b> ارتقا یافت.\n\n"
        f"💰 موجودی جدید: {new_user['coins']:,} سکه",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(user_id))
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if data.startswith("panel_upgrade:"):
        await upgrade_panel(update, context)
        return True
    if data.startswith("panel_confirm:"):
        await confirm_upgrade(update, context)
        return True
    return False