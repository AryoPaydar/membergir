from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    get_user, update_user, set_user_state, get_user_state,
    add_coins, remove_coins, check_membership, check_bot_admin,
    is_admin
)
from utils.keyboards import inline, back_button, main_menu
from utils.helpers import (
    is_positive_int, is_valid_username, normalize_channel, now_ts, format_number
)

# ==================== منوی سفارش ====================
async def order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    from bot_manager import get_setting
    if get_setting("order_locked", "off") == "on":
        await update.message.reply_text("❌ ثبت سفارش موقتاً غیرفعال است.")
        return
    
    # گرفتن آیتم‌های فعال از دیتابیس
    with db.conn() as c:
        items = c.execute("SELECT * FROM settings WHERE key LIKE 'order_item_%'").fetchall()
    
    if not items:
        await update.message.reply_text("❌ هنوز آیتم سفارشی تنظیم نشده است.")
        return
    
    rows = []
    for it in items:
        try:
            parts = it["value"].split("|")  # نام|سکه|عضو
            name, coin, member = parts[0], int(parts[1]), int(parts[2])
            rows.append([(f"{name} | {coin} سکه", f"order_pick:{it['key']}")])
        except Exception:
            continue
    rows.append([("🔙 بازگشت", "back")])
    await update.message.reply_text("📌 آیتم مورد نظر را انتخاب کنید:", reply_markup=inline(rows))

# ==================== انتخاب آیتم ====================
async def order_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    item_key = q.data.split(":", 1)[1]
    
    with db.conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key = ?", (item_key,)).fetchone()
    if not row:
        await q.message.reply_text("❌ آیتم یافت نشد.")
        return
    
    try:
        name, coin, member = row["value"].split("|")
        coin, member = int(coin), int(member)
    except Exception:
        await q.message.reply_text("❌ خطای آیتم.")
        return
    
    user = get_user(user_id)
    if user["coins"] < coin:
        await q.answer(f"❌ موجودی کافی نیست! ({coin} سکه لازم است)", show_alert=True)
        return
    
    set_user_state(user_id, "order_channel", {"name": name, "coin": coin, "member": member})
    await q.message.reply_text(
        "📢 آیدی کانال خود را ارسال کنید (بدون @):\n\n"
        "⚠️ حتماً ربات را ابتدا ادمین کانال کنید.",
        reply_markup=back_button()
    )

# ==================== دریافت کانال ====================
async def handle_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    state, data = get_user_state(user_id)
    if state != "order_channel":
        return False
    
    text = (update.message.text or "").strip()
    if text == "🔙 بازگشت":
        set_user_state(user_id, "none")
        await update.message.reply_text("🏠", reply_markup=main_menu())
        return True
    
    channel = normalize_channel(text)
    if not is_valid_username(channel):
        await update.message.reply_text("❌ آیدی کانال نامعتبر است.")
        return True
    
    # چک ادمین بودن ربات
    if not await check_bot_admin(context, channel):
        await update.message.reply_text(
            f"❌ ربات در کانال @{channel} ادمین نیست.\n"
            f"لطفاً ابتدا ربات را ادمین کنید و دوباره تلاش کنید."
        )
        return True
    
    # دریافت اطلاعات کانال
    try:
        chat = await context.bot.get_chat(f"@{channel}")
        if chat.type not in ("channel", "supergroup"):
            await update.message.reply_text("❌ فقط کانال یا سوپرگروه مجاز است.")
            return True
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در دریافت اطلاعات کانال: {e}")
        return True
    
    # ساخت پست تبلیغاتی
    name = data.get("name", "")
    coin = data.get("coin", 0)
    member = data.get("member", 0)
    
    if get_user(user_id)["coins"] < coin:
        await update.message.reply_text("❌ موجودی کافی نیست.")
        set_user_state(user_id, "none")
        return True
    
    # ارسال پست به کانال تبلیغات
    bot_username = (await context.bot.get_me()).username
    post_text = (
        f"‼️ نام کانال: {chat.title}\n\n"
        f"📝 توضیحات: {chat.description or 'ندارد'}\n\n"
        f"🆔 @{channel}"
    )
    
    button = inline([
        [(f"👤 سفارش {member} ممبر", "noop")],
        [("💰 دریافت سکه", "claim_coin:0")],  # order_id بعداً ست میشه
        [("📢 عضویت در کانال", f"https://t.me/{channel}")],
        [("🚫 گزارش", "report:0")],
    ])
    
    try:
        post = await context.bot.send_message(
            f"@{Config.ADS_CHANNEL}",
            post_text,
            reply_markup=button
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پست: {e}")
        return True
    
    # ذخیره سفارش در دیتابیس
    with db.conn() as c:
        cur = c.execute("""
            INSERT INTO orders (admin_id, channel, channel_id, post_id, member_target, coins_cost, cancel_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, channel, chat.id, post.message_id, member, coin, now_ts() + Config.CANCEL_WAIT_SECONDS))
        order_id = cur.lastrowid
    
    # آپدیت دکمه دریافت سکه با order_id واقعی
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=f"@{Config.ADS_CHANNEL}",
            message_id=post.message_id,
            reply_markup=inline([
                [(f"👤 سفارش {member} ممبر", "noop")],
                [("💰 دریافت سکه", f"claim_coin:{order_id}")],
                [("📢 عضویت در کانال", f"https://t.me/{channel}")],
                [("🚫 گزارش", f"report:{order_id}")],
            ])
        )
    except Exception:
        pass
    
    # کسر سکه و آپدیت کاربر
    remove_coins(user_id, coin, "order_create", f"سفارش #{order_id}")
    update_user(user_id, orders_count=(get_user(user_id)["orders_count"] + 1))
    
    set_user_state(user_id, "none")
    await update.message.reply_text(
        f"✅ سفارش شما با موفقیت ثبت شد.\n"
        f"🆔 کد پیگیری: <code>{order_id}</code>\n"
        f"👥 ممبر درخواستی: {member}\n"
        f"💰 هزینه: {coin} سکه",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(user_id))
    )
    return True

# ==================== دریافت سکه سفارش ====================
async def claim_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        order = c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            await q.answer("❌ سفارش یافت نشد.", show_alert=True)
            return
        order = dict(order)
        
        # چک تکراری نبودن
        dup = c.execute(
            "SELECT 1 FROM order_members WHERE order_id = ? AND user_id = ?",
            (order_id, user_id)
        ).fetchone()
        if dup:
            await q.answer("❌ قبلاً سکه این سفارش را گرفته‌اید.", show_alert=True)
            return
    
    if order["admin_id"] == user_id:
        await q.answer("❌ نمی‌توانید از سفارش خودتان سکه بگیرید.", show_alert=True)
        return
    
    if order["status"] != "running":
        await q.answer("❌ این سفارش فعال نیست.", show_alert=True)
        return
    
    if order["member_received"] >= order["member_target"]:
        await q.answer("❌ ظرفیت این سفارش پر شده.", show_alert=True)
        return
    
    # چک عضویت در کانال سفارش
    if not await check_membership(context, order["channel"], user_id):
        await q.answer("❌ ابتدا در کانال عضو شوید.", show_alert=True)
        return
    
    # چک عضویت در کانال تبلیغات
    if not await check_membership(context, Config.ADS_CHANNEL, user_id):
        await q.answer("❌ ابتدا در کانال تبلیغات عضو شوید.", show_alert=True)
        return
    
    user = get_user(user_id)
    coin = get_panel_join_coin(user["panel"])
    
    # ثبت عضو و افزایش شمارنده — به صورت اتمیک
    with db.conn() as c:
        # چک دوباره (race condition)
        dup = c.execute(
            "SELECT 1 FROM order_members WHERE order_id = ? AND user_id = ?",
            (order_id, user_id)
        ).fetchone()
        if dup:
            await q.answer("❌ قبلاً ثبت شده.", show_alert=True)
            return
        
        c.execute("""
            INSERT INTO order_members (order_id, user_id)
            VALUES (?, ?)
        """, (order_id, user_id))
        
        c.execute("""
            UPDATE orders SET member_received = member_received + 1
            WHERE id = ? AND member_received < member_target
        """, (order_id,))
        
        # افزایش شمارنده عضویت کاربر
        c.execute("UPDATE users SET ads_joined = ads_joined + 1 WHERE user_id = ?", (user_id,))
    
    # افزودن سکه
    add_coins(user_id, coin, "order_join", f"عضویت در سفارش #{order_id}")
    
    new_coins = get_user(user_id)["coins"]
    await q.answer(f"✅ {coin} سکه دریافت کردید!\n💰 موجودی: {new_coins:,}", show_alert=False)
    
    # بررسی اتمام سفارش
    with db.conn() as c:
        o = c.execute("SELECT member_received, member_target, post_id, admin_id, channel FROM orders WHERE id=?", (order_id,)).fetchone()
        if o and o["member_received"] >= o["member_target"]:
            c.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
            try:
                await context.bot.delete_message(f"@{Config.ADS_CHANNEL}", o["post_id"])
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    o["admin_id"],
                    f"✅ سفارش #{order_id} برای کانال @{o['channel']} به پایان رسید."
                )
            except Exception:
                pass
    
    # پورسانت زیرمجموعه
    await handle_referral_commission(context, user_id, order_id)

async def get_panel_join_coin(panel):
    return Config.PANELS.get(panel, Config.PANELS["عادی"])["join_coin"]

async def handle_referral_commission(context, user_id, order_id):
    """پورسانت به معرف در صورت رسیدن به آستانه"""
    user = get_user(user_id)
    if not user or not user["referrer_id"]:
        return
    from bot_manager import get_setting, add_coins
    threshold = int(get_setting("referral_join_threshold", str(Config.REFERRAL_JOIN_THRESHOLD)))
    coin = int(get_setting("referral_join_coin", str(Config.REFERRAL_JOIN_COIN)))
    
    if user["ads_joined"] == threshold:
        add_coins(user["referrer_id"], coin, "referral_commission", f"پورسانت از {user_id}")
        try:
            await context.bot.send_message(
                user["referrer_id"],
                f"🎉 زیرمجموعه شما ({user_id}) به {threshold} عضویت رسید!\n"
                f"💰 {coin} سکه پورسانت دریافت کردید."
            )
        except Exception:
            pass

# ==================== گزارش ====================
async def report_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])
    with db.conn() as c:
        if c.execute("SELECT 1 FROM order_reports WHERE order_id=? AND reporter_id=?", (order_id, user_id)).fetchone():
            await q.answer("❌ قبلاً گزارش داده‌اید.", show_alert=True)
            return
        c.execute("INSERT INTO order_reports (order_id, reporter_id) VALUES (?, ?)", (order_id, user_id))
        o = c.execute("SELECT admin_id, channel FROM orders WHERE id=?", (order_id,)).fetchone()
    
    await q.answer("✅ گزارش شما ثبت شد.", show_alert=True)
    if o:
        try:
            await context.bot.send_message(
                Config.ADMIN_ID,
                f"🚫 گزارش جدید\nسفارش #{order_id}\n"
                f"سفارش‌دهنده: {o['admin_id']}\n"
                f"گزارش‌دهنده: {user_id}\n"
                f"کانال: @{o['channel']}"
            )
        except Exception:
            pass

# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    if data.startswith("order_pick:"):
        await order_pick(update, context)
        return True
    if data.startswith("claim_coin:"):
        await claim_coin(update, context)
        return True
    if data.startswith("report:"):
        await report_order(update, context)
        return True
    return False