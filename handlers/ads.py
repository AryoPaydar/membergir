from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from database import db
from bot_manager import (
    get_user, update_user, set_user_state, get_user_state,
    add_coins, remove_coins, check_membership, check_bot_admin,
    is_admin, check_referral_milestone
)
from utils.keyboards import inline, back_button, main_menu
from utils.helpers import (
    is_positive_int, is_valid_username, normalize_channel, now_ts, format_number
)


# ==================== آیتم‌های ثابت ثبت سفارش ====================
ORDER_ITEMS = [
    {"key": "item_20",   "members": 20,   "coins": 40},
    {"key": "item_10",   "members": 10,   "coins": 20},
    {"key": "item_100",  "members": 100,  "coins": 200},
    {"key": "item_50",   "members": 50,   "coins": 100},
    {"key": "item_400",  "members": 400,  "coins": 800},
    {"key": "item_200",  "members": 200,  "coins": 400},
]


# ==================== منوی سفارش ====================
async def order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    from bot_manager import get_setting
    
    if get_setting("order_locked", "off") == "on":
        await update.message.reply_text("❌ ثبت سفارش موقتاً غیرفعال است.")
        return
    
    text = "❓مقدار ممبر درخواستی خود را انتخاب کنید"
    
    # ساخت دکمه‌ها به صورت ۲ تا در هر ردیف
    rows = []
    for i in range(0, len(ORDER_ITEMS), 2):
        row = []
        for item in ORDER_ITEMS[i:i+2]:
            btn_text = f"👤 {item['members']} نفر = {item['coins']} الماس 💎"
            row.append((btn_text, f"order_pick:{item['key']}"))
        rows.append(row)
    
    await update.message.reply_text(
        text,
        reply_markup=inline(rows)
    )


# ==================== انتخاب آیتم ====================
async def order_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    item_key = q.data.split(":", 1)[1]
    
    # پیدا کردن آیتم
    item = None
    for it in ORDER_ITEMS:
        if it["key"] == item_key:
            item = it
            break
    
    if not item:
        await q.answer("❌ آیتم یافت نشد.", show_alert=True)
        return
    
    # چک موجودی
    user = get_user(user_id)
    if user["coins"] < item["coins"]:
        await q.answer("❌ الماس شما کافی نیست", show_alert=True)
        return
    
    await q.answer()
    
    # ذخیره state و نمایش پیام درخواست کانال
    set_user_state(user_id, "order_channel", {
        "members": item["members"],
        "coins": item["coins"],
        "key": item_key,
    })
    
    text = (
        "✅جهت دریافت ممبر باید ابتدا ربات را ادمین کانال مورد نظر کنید سپس آیدی کانال را ارسال نمایید\n"
        "\n"
        "👈نمونه : @durov\n"
        "\n"
        "📌درصورتی که مشکلی در ادمین کردن ربات دارید دستور زیر را ارسال نمایید\n"
        "/help"
    )
    
    await q.message.reply_text(text, reply_markup=back_button())


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
    
    # نرمال‌سازی آیدی کانال
    channel = normalize_channel(text)
    
    # چک معتبر بودن آیدی
    if not is_valid_username(channel):
        await update.message.reply_text(
            "❌آیدی ارسالی صحیح نمی باشد\n"
            "\n"
            "👈نمونه : @durov"
        )
        return True
    
    # چک ادمین بودن ربات در کانال
    if not await check_bot_admin(context, channel):
        await update.message.reply_text(
            f"❌ربات ادمین کانال @{channel} نیست\n"
            f"\n"
            f"👈جهت دریافت ممبر باید ابتدا ربات را ادمین کانال مورد نظر کنید سپس آیدی کانال خود را ارسال نمایید\n"
            f"\n"
            f"📌درصورتی که مشکلی در ادمین کردن ربات دارید دستور زیر را ارسال نمایید\n"
            f"/help"
        )
        return True
    
    # دریافت اطلاعات کانال
    try:
        chat = await context.bot.get_chat(f"@{channel}")
        if chat.type not in ("channel", "supergroup"):
            await update.message.reply_text(
                "❌آیدی ارسالی صحیح نمی باشد\n"
                "\n"
                "👈نمونه : @durov"
            )
            return True
    except Exception:
        await update.message.reply_text(
            "❌آیدی ارسالی صحیح نمی باشد\n"
            "\n"
            "👈نمونه : @durov"
        )
        return True
    
    members = data.get("members", 0)
    coins = data.get("coins", 0)
    
    # ذخیره اطلاعات کانال در state
    set_user_state(user_id, "order_confirm", {
        "members": members,
        "coins": coins,
        "channel": channel,
        "channel_title": chat.title,
        "channel_desc": chat.description or "ندارد",
        "channel_id": chat.id,
    })
    
    # پیام اول: اطلاعات کانال
    post_text = (
        f"‼️نام کانال : {chat.title}\n"
        f"\n"
        f"📝توضیحات کانال: {chat.description or 'ندارد'}\n"
        f"\n"
        f"🆔@{channel}"
    )
    
    sent = await update.message.reply_text(post_text, reply_markup=back_button())
    
    # پیام دوم: تأیید (با ریپلای)
    confirm_text = (
        f"👈آیا از درخواست {members} ممبر برای کانال فوق اطمینان دارید⁉️"
    )
    
    await update.message.reply_text(
        confirm_text,
        reply_to_message_id=sent.message_id,
        reply_markup=inline([
            [("✅ بله", f"order_confirm_yes:{sent.message_id}"),
             ("❌ خیر", "order_confirm_no")],
        ])
    )
    return True


# ==================== تأیید نهایی سفارش ====================
async def order_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    state, data = get_user_state(user_id)
    
    if state != "order_confirm":
        await q.answer("❌ خطا. لطفاً دوباره تلاش کنید.", show_alert=True)
        return
    
    members = data.get("members", 0)
    coins = data.get("coins", 0)
    channel = data.get("channel", "")
    channel_id = data.get("channel_id")
    channel_title = data.get("channel_title", "")
    channel_desc = data.get("channel_desc", "ندارد")
    
    # چک موجودی دوباره
    user = get_user(user_id)
    if user["coins"] < coins:
        await q.answer("❌ الماس شما کافی نیست", show_alert=True)
        set_user_state(user_id, "none")
        return
    
    await q.answer()
    
    # ساخت پست تبلیغاتی
    bot_username = (await context.bot.get_me()).username
    post_text = (
        f"‼️نام کانال : {channel_title}\n"
        f"\n"
        f"📝توضیحات کانال: {channel_desc}\n"
        f"\n"
        f"🆔@{channel}"
    )
    
    button = inline([
        [(f"👤 سفارش {members} ممبر", "noop")],
        [("💰 دریافت سکه", "claim_coin:0")],
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
        await q.message.reply_text(f"❌ خطا در ارسال پست: {e}")
        set_user_state(user_id, "none")
        return
    
    # ذخیره سفارش در دیتابیس
    with db.conn() as c:
        cur = c.execute("""
            INSERT INTO orders (admin_id, channel, channel_id, post_id, member_target, coins_cost, cancel_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, channel, channel_id, post.message_id, members, coins, now_ts() + Config.CANCEL_WAIT_SECONDS))
        order_id = cur.lastrowid
    
    # آپدیت دکمه‌های پست با order_id واقعی
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=f"@{Config.ADS_CHANNEL}",
            message_id=post.message_id,
            reply_markup=inline([
                [(f"👤 سفارش {members} ممبر", "noop")],
                [("💰 دریافت سکه", f"claim_coin:{order_id}")],
                [("📢 عضویت در کانال", f"https://t.me/{channel}")],
                [("🚫 گزارش", f"report:{order_id}")],
            ])
        )
    except Exception:
        pass
    
    # کسر الماس
    remove_coins(user_id, coins, "order_create", f"سفارش #{order_id}")
    update_user(user_id, orders_count=(get_user(user_id)["orders_count"] + 1))
    
    set_user_state(user_id, "none")
    
    await q.message.reply_text(
        f"✅ سفارش شما با موفقیت ثبت شد.\n"
        f"🆔 کد پیگیری: <code>{order_id}</code>\n"
        f"👥 ممبر درخواستی: {members}\n"
        f"💰 هزینه: {coins} الماس",
        parse_mode="HTML",
        reply_markup=main_menu(is_admin(user_id))
    )


# ==================== لغو تأیید ====================
async def order_confirm_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    set_user_state(user_id, "none")
    await q.answer("لغو شد.")
    try:
        await q.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        user_id,
        "🏠 منوی اصلی",
        reply_markup=main_menu(is_admin(user_id))
    )


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
    
    if not await check_membership(context, order["channel"], user_id):
        await q.answer("❌ ابتدا در کانال عضو شوید.", show_alert=True)
        return
    
    if not await check_membership(context, Config.ADS_CHANNEL, user_id):
        await q.answer("❌ ابتدا در کانال تبلیغات عضو شوید.", show_alert=True)
        return
    
    user = get_user(user_id)
    coin = get_panel_join_coin(user["panel"])
    
    with db.conn() as c:
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
        
        c.execute("UPDATE users SET ads_joined = ads_joined + 1 WHERE user_id = ?", (user_id,))
    
    # بررسی پاداش زیرمجموعه
    await check_referral_milestone(context, user_id)
    
    add_coins(user_id, coin, "order_join", f"عضویت در سفارش #{order_id}")
    
    new_coins = get_user(user_id)["coins"]
    await q.answer(f"✅ {coin} سکه دریافت کردید!\n💰 موجودی: {new_coins:,}", show_alert=False)
    
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


async def get_panel_join_coin(panel):
    return Config.PANELS.get(panel, "عادی")["join_coin"]


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
    if data.startswith("order_confirm_yes:"):
        await order_confirm_yes(update, context)
        return True
    if data == "order_confirm_no":
        await order_confirm_no(update, context)
        return True
    if data.startswith("claim_coin:"):
        await claim_coin(update, context)
        return True
    if data.startswith("report:"):
        await report_order(update, context)
        return True
    return False
