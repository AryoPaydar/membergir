from telegram import Update
from telegram.ext import ContextTypes
from database import db
from bot_manager import is_admin, set_user_state, get_user_state
from utils.keyboards import inline, back_button, admin_panel
from utils.helpers import is_positive_int


async def orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    set_user_state(update.effective_user.id, "none")
    
    with db.conn() as c:
        items = c.execute("SELECT * FROM order_items ORDER BY position").fetchall()
    
    rows = []
    for it in items:
        rows.append([
            (f"✏️ {it['name']}", f"aor_edit:{it['key']}"),
        ])
    rows.append([("➕ افزودن آیتم", "aor_add")])
    rows.append([("🔙 بازگشت به پنل مدیریت", "aor_back")])
    
    await update.message.reply_text(
        "💢 به بخش تنظیمات آیتم های سفارش ممبر خوش آمدید\n\n"
        "👈در این بخش میتوانید آیتم‌های سفارش را مدیریت کنید",
        reply_markup=inline(rows)
    )


async def aor_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    set_user_state(q.from_user.id, "none")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(q.from_user.id, "👑 پنل مدیریت", reply_markup=admin_panel())


async def orders_menu_refresh(update, context):
    """رفرش لیست آیتم‌ها"""
    q = update.callback_query
    with db.conn() as c:
        items = c.execute("SELECT * FROM order_items ORDER BY position").fetchall()
    
    rows = []
    for it in items:
        rows.append([(f"✏️ {it['name']}", f"aor_edit:{it['key']}")])
    rows.append([("➕ افزودن آیتم", "aor_add")])
    rows.append([("🔙 بازگشت به پنل مدیریت", "aor_back")])
    
    try:
        await q.message.edit_text(
            "💢 تنظیمات آیتم‌های سفارش\n\nآیتم مورد نظر را برای ویرایش انتخاب کنید:",
            reply_markup=inline(rows)
        )
    except Exception:
        pass


# ==================== State Handler ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return False
    
    state, data = get_user_state(user_id)
    text = (update.message.text or "").strip()
    
    if not state or state == "none":
        return False
    
    if text == "🔙 بازگشت":
        set_user_state(user_id, "none")
        await update.message.reply_text("👑 پنل مدیریت", reply_markup=admin_panel())
        return True
    
    # === ویرایش نام ===
    if state.startswith("aor_set_name_"):
        key = state.replace("aor_set_name_", "")
        with db.conn() as c:
            c.execute("UPDATE order_items SET name = ? WHERE key = ?", (text, key))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ نام آیتم ویرایش شد.", reply_markup=admin_panel())
        return True
    
    # === ویرایش تعداد ممبر ===
    if state.startswith("aor_set_members_"):
        key = state.replace("aor_set_members_", "")
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        with db.conn() as c:
            c.execute("UPDATE order_items SET members = ? WHERE key = ?", (int(text), key))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ تعداد ممبر ویرایش شد.", reply_markup=admin_panel())
        return True
    
    # === ویرایش سکه ===
    if state.startswith("aor_set_coins_"):
        key = state.replace("aor_set_coins_", "")
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        with db.conn() as c:
            c.execute("UPDATE order_items SET coins = ? WHERE key = ?", (int(text), key))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ تعداد سکه ویرایش شد.", reply_markup=admin_panel())
        return True
    
    # === حذف آیتم ===
    if state.startswith("aor_del_"):
        key = state.replace("aor_del_", "")
        with db.conn() as c:
            c.execute("DELETE FROM order_items WHERE key = ?", (key,))
        set_user_state(user_id, "none")
        await update.message.reply_text("✅ آیتم حذف شد.", reply_markup=admin_panel())
        return True
    
    # === افزودن آیتم — مرحله ۱: کلید ===
    if state == "aor_add_key":
        # چک یکتا بودن
        with db.conn() as c:
            existing = c.execute("SELECT 1 FROM order_items WHERE key = ?", (text,)).fetchone()
        if existing:
            await update.message.reply_text(
                "❌ این کلید قبلاً استفاده شده. کلید دیگری وارد کنید:",
                reply_markup=back_button()
            )
            return True
        
        set_user_state(user_id, "aor_add_name", {"key": text})
        await update.message.reply_text(
            "نام نمایشی برای آیتم جدید وارد کنید (مثل: 👤 500 ممبر):",
            reply_markup=back_button()
        )
        return True
    
    # === افزودن آیتم — مرحله ۲: نام ===
    if state == "aor_add_name":
        key = data.get("key")
        set_user_state(user_id, "aor_add_members", {"key": key, "name": text})
        await update.message.reply_text(
            "تعداد ممبر این آیتم را وارد کنید (مثل: 500):",
            reply_markup=back_button()
        )
        return True
    
    # === افزودن آیتم — مرحله ۳: تعداد ممبر ===
    if state == "aor_add_members":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        set_user_state(user_id, "aor_add_coins", {**data, "members": int(text)})
        await update.message.reply_text(
            "تعداد سکه (الماس) این آیتم را وارد کنید (مثل: 1000):",
            reply_markup=back_button()
        )
        return True
    
    # === افزودن آیتم — مرحله ۴: تعداد سکه (ذخیره نهایی) ===
    if state == "aor_add_coins":
        if not is_positive_int(text):
            await update.message.reply_text("❌ فقط عدد مجاز است.")
            return True
        
        key = data.get("key")
        name = data.get("name")
        members = data.get("members")
        coins = int(text)
        
        # موقعیت: آخرین + ۱
        with db.conn() as c:
            pos_row = c.execute("SELECT COALESCE(MAX(position), 0) as max_pos FROM order_items").fetchone()
            new_pos = (pos_row["max_pos"] or 0) + 1
            c.execute("""
                INSERT INTO order_items (key, name, members, coins, position)
                VALUES (?, ?, ?, ?, ?)
            """, (key, name, members, coins, new_pos))
        
        set_user_state(user_id, "none")
        await update.message.reply_text(
            f"✅ آیتم جدید اضافه شد:\n\n"
            f"🔑 کلید: {key}\n"
            f"📝 نام: {name}\n"
            f"👥 ممبر: {members}\n"
            f"💰 سکه: {coins}",
            reply_markup=admin_panel()
        )
        return True
    
    return False


# ==================== Callback Handler ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if not is_admin(q.from_user.id):
        return False
    
    if data.startswith("aor_edit:"):
        await q.answer()
        key = data.split(":")[1]
        with db.conn() as c:
            it = c.execute("SELECT * FROM order_items WHERE key = ?", (key,)).fetchone()
        if not it:
            return True
        try:
            await q.message.edit_text(
                f"آیتم: {it['name']}\n"
                f"👥 ممبر: {it['members']}\n"
                f"💰 سکه: {it['coins']}\n\n"
                f"کدام فیلد را ویرایش می‌کنید؟",
                reply_markup=inline([
                    [("📝 نام", f"aor_name:{key}"), ("👥 ممبر", f"aor_members:{key}")],
                    [("💰 سکه", f"aor_coins:{key}")],
                    [("🗑 حذف", f"aor_del:{key}")],
                    [("🔙 بازگشت", "aor_menu")],
                ])
            )
        except Exception:
            pass
        return True
    
    if data.startswith("aor_name:"):
        await q.answer()
        key = data.split(":")[1]
        set_user_state(q.from_user.id, f"aor_set_name_{key}")
        await q.message.reply_text("نام جدید را وارد کنید:", reply_markup=back_button())
        return True
    
    if data.startswith("aor_members:"):
        await q.answer()
        key = data.split(":")[1]
        set_user_state(q.from_user.id, f"aor_set_members_{key}")
        await q.message.reply_text("تعداد ممبر جدید را وارد کنید:", reply_markup=back_button())
        return True
    
    if data.startswith("aor_coins:"):
        await q.answer()
        key = data.split(":")[1]
        set_user_state(q.from_user.id, f"aor_set_coins_{key}")
        await q.message.reply_text("تعداد سکه جدید را وارد کنید:", reply_markup=back_button())
        return True
    
    if data.startswith("aor_del:"):
        await q.answer()
        key = data.split(":")[1]
        with db.conn() as c:
            c.execute("DELETE FROM order_items WHERE key = ?", (key,))
        await q.answer("✅ حذف شد.", show_alert=True)
        # بازگشت به لیست
        q.data = "aor_menu"
        await orders_menu_refresh(update, context)
        return True
    
    if data == "aor_menu":
        await q.answer()
        await orders_menu_refresh(update, context)
        return True
    
    if data == "aor_add":
        await q.answer()
        set_user_state(q.from_user.id, "aor_add_key")
        await q.message.reply_text(
            "کلید یکتای انگلیسی برای آیتم جدید وارد کنید (مثل item_500):",
            reply_markup=back_button()
        )
        return True
    
    if data == "aor_back":
        await aor_back(update, context)
        return True
    return False
