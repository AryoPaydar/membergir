from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import is_admin, set_user_state, get_user_state
from utils.keyboards import inline, admin_panel, back_button
from utils.helpers import is_positive_int, format_number

# ==================== منوی اصلی فروشگاه ادمین ====================
async def shop_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🛍 <b>مدیریت فروشگاه</b>\n\nگزینه مورد نظر را انتخاب کنید:",
        parse_mode="HTML",
        reply_markup=inline([
            [("💰 آیتم‌های سکه", "admin_shop_coins")],
            [("♻️ آیتم‌های پنل", "admin_shop_panels")],
            [("💵 موجودی فروشگاه", "admin_shop_balance")],
            [("💳 تسویه حساب", "admin_shop_settle")],
            [("📇 متن‌های فروشگاه", "admin_shop_texts")],
            [("🔙 بازگشت", "admin_back")],
        ])
    )

# ==================== آیتم‌های سکه ====================
async def list_coin_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    
    with db.conn() as c:
        items = c.execute(
            "SELECT * FROM shop_items WHERE item_type='coin' ORDER BY position, id"
        ).fetchall()
    
    if not items:
        await q.message.edit_text(
            "💰 هنوز آیتم سکه‌ای تنظیم نشده.\n\nبرای افزودن دکمه زیر را بزنید:",
            reply_markup=inline([
                [("➕ افزودن آیتم", "admin_shop_coin_add")],
                [("🔙 بازگشت", "admin_shop_back")],
            ])
        )
        return
    
    text = "💰 <b>آیتم‌های سکه:</b>\n\n"
    rows = []
    for i, it in enumerate(items, 1):
        text += f"{i}. {it['name']} | {it['coin_amount']} سکه | {format_number(it['price'])} ریال\n"
        rows.append([
            (f"✏️ {it['name']}", f"admin_shop_coin_edit:{it['id']}"),
            ("🗑", f"admin_shop_coin_del:{it['id']}"),
        ])
    rows.append([("➕ افزودن آیتم", "admin_shop_coin_add")])
    rows.append([("🔙 بازگشت", "admin_shop_back")])
    
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=inline(rows))

async def add_coin_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "admin_shop_coin_add_name")
    await q.message.edit_text("📝 نام آیتم را وارد کنید (مثلاً: ۵۰۰ سکه):")

async def edit_coin_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        it = c.execute("SELECT * FROM shop_items WHERE id=?", (item_id,)).fetchone()
    if not it:
        await q.message.edit_text("❌ یافت نشد.")
        return
    
    await q.message.edit_text(
        f"💰 <b>{it['name']}</b>\n\n"
        f"💵 قیمت: {format_number(it['price'])} ریال\n"
        f"🪙 مقدار سکه: {it['coin_amount']}\n\n"
        f"کدام فیلد را ویرایش می‌کنید؟",
        parse_mode="HTML",
        reply_markup=inline([
            [("📝 نام", f"admin_shop_coin_edit_name:{item_id}"),
             ("💵 قیمت", f"admin_shop_coin_edit_price:{item_id}")],
            [("🪙 مقدار سکه", f"admin_shop_coin_edit_amount:{item_id}")],
            [("🗑 حذف", f"admin_shop_coin_del:{item_id}")],
            [("🔙 بازگشت", "admin_shop_coins")],
        ])
    )

async def delete_coin_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split(":")[1])
    with db.conn() as c:
        c.execute("DELETE FROM shop_items WHERE id=?", (item_id,))
    await q.answer("✅ حذف شد.", show_alert=True)
    await list_coin_items(update, context)

# ==================== آیتم‌های پنل ====================
async def list_panel_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    with db.conn() as c:
        items = c.execute(
            "SELECT * FROM shop_items WHERE item_type='panel' ORDER BY position, id"
        ).fetchall()
    
    if not items:
        await q.message.edit_text(
            "♻️ هنوز آیتم پنلی تنظیم نشده.",
            reply_markup=inline([
                [("➕ افزودن آیتم", "admin_shop_panel_add")],
                [("🔙 بازگشت", "admin_shop_back")],
            ])
        )
        return
    
    text = "♻️ <b>آیتم‌های پنل:</b>\n\n"
    rows = []
    for i, it in enumerate(items, 1):
        text += f"{i}. {it['name']} | {it['panel_name']} {it['panel_days']} روز | {format_number(it['price'])} ریال\n"
        rows.append([
            (f"✏️ {it['name']}", f"admin_shop_panel_edit:{it['id']}"),
            ("🗑", f"admin_shop_panel_del:{it['id']}"),
        ])
    rows.append([("➕ افزودن آیتم", "admin_shop_panel_add")])
    rows.append([("🔙 بازگشت", "admin_shop_back")])
    
    await q.message.edit_text(text, parse_mode="HTML", reply_markup=inline(rows))

async def add_panel_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "admin_shop_panel_add_name")
    await q.message.edit_text("📝 نام آیتم را وارد کنید (مثلاً: پنل حرفه‌ای ۳۰ روز):")

# ==================== موجودی و تسویه ====================
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    from bot_manager import get_setting
    balance = int(get_setting("shop_balance", "0"))
    await q.message.edit_text(
        f"💵 <b>موجودی فروشگاه</b>\n\n💰 {format_number(balance)} ریال",
        parse_mode="HTML",
        reply_markup=inline([[("🔙 بازگشت", "admin_shop_back")]])
    )

async def settle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    from bot_manager import get_setting
    balance = int(get_setting("shop_balance", "0"))
    if balance < 200000:
        await q.answer("❌ حداقل موجودی برای تسویه ۲۰۰,۰۰۰ ریال است.", show_alert=True)
        return
    set_user_state(q.from_user.id, "admin_settle_card")
    await q.message.edit_text(
        f"💳 مبلغ قابل تسویه: {format_number(balance)} ریال\n\n"
        f"👈 شماره کارت ۱۶ رقمی خود را ارسال کنید:"
    )

# ==================== متن‌های فروشگاه ====================
async def shop_texts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        "📇 <b>متن‌های فروشگاه</b>\n\nکدام متن را ویرایش می‌کنید؟",
        parse_mode="HTML",
        reply_markup=inline([
            [("متن اصلی فروشگاه", "admin_set_text:shop_main_text")],
            [("متن خرید سکه", "admin_set_text:shop_coin_text")],
            [("متن خرید پنل", "admin_set_text:shop_panel_text")],
            [("🔙 بازگشت", "admin_shop_back")],
        ])
    )

# ==================== بازگشت ====================
async def shop_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "🛍 مدیریت فروشگاه", reply_markup=admin_panel())

# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if not state or state == "none":
        return False
    
    # === افزودن آیتم سکه ===
    if state == "admin_shop_coin_add_name":
        set_user_state(user_id, "admin_shop_coin_add_price", {"name": text})
        await update.message.reply_text("💵 قیمت به ریال را وارد کنید:")
        return True
    
    if state == "admin_shop_coin_add_price":
        if not is_positive_int(text) or int(text) < 10000:
            await update.message.reply_text("❌ عدد معتبر (حداقل ۱۰,۰۰۰) وارد کنید.")
            return True
        set_user_state(user_id, "admin_shop_coin_add_amount", {**data, "price": int(text)})
        await update.message.reply_text("🪙 مقدار سکه را وارد کنید:")
        return True
    
    if state == "admin_shop_coin_add_amount":
        if not is_positive_int(text):
            await update.message.reply_text("❌ عدد معتبر وارد کنید.")
            return True
        with db.conn() as c:
            c.execute("""
                INSERT INTO shop_items (item_type, name, price, coin_amount, position)
                VALUES ('coin', ?, ?, ?, ?)
            """, (data["name"], data["price"], int(text), 99))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ آیتم اضافه شد.")
        await context.bot.send_message(user_id, "🛍 مدیریت فروشگاه", reply_markup=admin_panel())
        return True
    
    # === ویرایش نام آیتم سکه ===
    if state == "admin_shop_coin_edit_name":
        item_id = data["item_id"]
        with db.conn() as c:
            c.execute("UPDATE shop_items SET name=? WHERE id=?", (text, item_id))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ نام ویرایش شد.")
        return True
    
    if state == "admin_shop_coin_edit_price":
        item_id = data["item_id"]
        if not is_positive_int(text):
            await update.message.reply_text("❌ عدد معتبر.")
            return True
        with db.conn() as c:
            c.execute("UPDATE shop_items SET price=? WHERE id=?", (int(text), item_id))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ قیمت ویرایش شد.")
        return True
    
    if state == "admin_shop_coin_edit_amount":
        item_id = data["item_id"]
        if not is_positive_int(text):
            await update.message.reply_text("❌ عدد معتبر.")
            return True
        with db.conn() as c:
            c.execute("UPDATE shop_items SET coin_amount=? WHERE id=?", (int(text), item_id))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ مقدار سکه ویرایش شد.")
        return True
    
    # === افزودن آیتم پنل ===
    if state == "admin_shop_panel_add_name":
        set_user_state(user_id, "admin_shop_panel_add_panel", {"name": text})
        await update.message.reply_text(
            "🎖 نوع پنل را انتخاب کنید:",
            reply_markup=inline([
                [("عادی", "panel_choice:عادی"), ("حرفه ای", "panel_choice:حرفه ای"), ("ویژه", "panel_choice:ویژه")],
            ])
        )
        return True
    
    if state == "admin_shop_panel_add_days":
        set_user_state(user_id, "admin_shop_panel_add_price", {**data, "days": int(text)})
        await update.message.reply_text("💵 قیمت به ریال را وارد کنید:")
        return True
    
    if state == "admin_shop_panel_add_price":
        if not is_positive_int(text) or int(text) < 10000:
            await update.message.reply_text("❌ عدد معتبر وارد کنید.")
            return True
        with db.conn() as c:
            c.execute("""
                INSERT INTO shop_items (item_type, name, price, panel_name, panel_days, position)
                VALUES ('panel', ?, ?, ?, ?, ?)
            """, (data["name"], int(text), data["panel"], data["days"], 99))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ آیتم پنل اضافه شد.")
        await context.bot.send_message(user_id, "🛍 مدیریت فروشگاه", reply_markup=admin_panel())
        return True
    
    # === تسویه حساب ===
    if state == "admin_settle_card":
        if not is_positive_int(text) or len(text) != 16:
            await update.message.reply_text("❌ شماره کارت ۱۶ رقمی وارد کنید.")
            return True
        from bot_manager import get_setting, set_setting
        balance = int(get_setting("shop_balance", "0"))
        # ارسال به ادمین اصلی
        try:
            await context.bot.send_message(
                Config.ADMIN_ID,
                f"💳 درخواست تسویه\n\n"
                f"👤 ادمین: {user_id}\n"
                f"💰 مبلغ: {format_number(balance)} ریال\n"
                f"💳 کارت: <code>{text}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        set_setting("shop_balance", "0")
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ درخواست تسویه ثبت شد.")
        return True
    
    return False

# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    handlers = {
        "admin_shop_coins": list_coin_items,
        "admin_shop_panels": list_panel_items,
        "admin_shop_balance": show_balance,
        "admin_shop_settle": settle_start,
        "admin_shop_texts": shop_texts_menu,
        "admin_shop_back": shop_back,
        "admin_shop_coin_add": add_coin_item,
        "admin_shop_panel_add": add_panel_item,
    }
    if data in handlers:
        await handlers[data](update, context)
        return True
    
    if data.startswith("admin_shop_coin_edit:"):
        await edit_coin_item(update, context)
        return True
    if data.startswith("admin_shop_coin_del:"):
        await delete_coin_item(update, context)
        return True
    if data.startswith("admin_shop_coin_edit_name:"):
        await q.answer()
        item_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "admin_shop_coin_edit_name", {"item_id": item_id})
        await q.message.edit_text("📝 نام جدید:")
        return True
    if data.startswith("admin_shop_coin_edit_price:"):
        await q.answer()
        item_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "admin_shop_coin_edit_price", {"item_id": item_id})
        await q.message.edit_text("💵 قیمت جدید:")
        return True
    if data.startswith("admin_shop_coin_edit_amount:"):
        await q.answer()
        item_id = int(data.split(":")[1])
        set_user_state(q.from_user.id, "admin_shop_coin_edit_amount", {"item_id": item_id})
        await q.message.edit_text("🪙 مقدار سکه جدید:")
        return True
    if data.startswith("panel_choice:"):
        await q.answer()
        panel = data.split(":", 1)[1]
        set_user_state(q.from_user.id, "admin_shop_panel_add_days", {"name": "در انتظار", "panel": panel})
        await q.message.edit_text("⏳ چند روز؟")
        return True
    
    return False