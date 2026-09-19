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


# ==================== تابع دریافت سکه عضویت (sync) ====================
def get_panel_join_coin(panel):
    return Config.PANELS.get(panel, "عادی")["join_coin"]


# ==================== منوی سفارش ====================
async def order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    from bot_manager import get_setting
    
    if get_setting("order_locked", "off") == "on":
        await update.message.reply_text("❌ ثبت سفارش موقتاً غیرفعال است.")
        return
    
    # 👇 از دیتابیس بخون
    with db.conn() as c:
        items = c.execute("SELECT * FROM order_items ORDER BY position").fetchall()
    
    if not items:
        await update.message.reply_text("❌ هنوز آیتمی تنظیم نشده.")
        return
    
    text = "❓مقدار ممبر درخواستی خود را انتخاب کنید"
    
    rows = []
    for i in range(0, len(items), 2):
        row = []
        for it in items[i:i+2]:
            btn_text = f"👤 {it['members']} نفر = {it['coins']} الماس 💎"
            row.append((btn_text, f"order_pick:{it['key']}"))
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
    
    # 👇 از دیتابیس بخون
    with db.conn() as c:
        item = c.execute("SELECT * FROM order_items WHERE key = ?", (item_key,)).fetchone()
    
    if not item:
        await q.answer("❌ آیتم یافت نشد.", show_alert=True)
        return
    
    item = dict(item)
    
    user = get_user(user_id)
    if not user or user["coins"] < item["coins"]:
        await q.answer("❌ الماس شما کافی نیست", show_alert=True)
        return
    
    await q.answer()
    
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


# ==================== چک معتبر بودن آیدی (فقط با @) ====================
def is_valid_at_channel(text: str) -> bool:
    if not text or not text.startswith("@"):
        return False
    import re
    return bool(re.match(r"^@[a-zA-Z0-9_]{5,32}$", text.strip()))


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
    
    if not is_valid_at_channel(text):
        await update.message.reply_text(
            "❌آیدی ارسالی صحیح نمی باشد\n"
            "\n"
            "👈نمونه : @durov"
        )
        return True
    
    channel = text[1:]
    
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
    
    set_user_state(user_id, "order_confirm", {
        "members": members,
        "coins": coins,
        "channel": channel,
        "channel_title": chat.title,
        "channel_desc": chat.description or "ندارد",
        "channel_id": chat.id,
    })
    
    post_text = (
        f"‼️نام کانال : {chat.title}\n"
        f"\n"
        f"📝توضیحات کانال: {chat.description or 'ندارد'}\n"
        f"\n"
        f"🆔@{channel}"
    )
    
    sent = await update.message.reply_text(post_text, reply_markup=back_button())
    
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
    
    user = get_user(user_id)
    if not user or user["coins"] < coins:
        await q.answer("❌ الماس شما کافی نیست", show_alert=True)
        set_user_state(user_id, "none")
        return
    
    await q.answer()
    
    try:
        await q.message.delete()
    except Exception:
        pass
    
    with db.conn() as c:
        cur = c.execute("""
            INSERT INTO orders (admin_id, channel, channel_id, post_id, member_target, coins_cost, cancel_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, channel, channel_id, None, members, coins, now_ts() + Config.CANCEL_WAIT_SECONDS))
        order_id = cur.lastrowid
    
    post_text = (
        f"‼️نام کانال : {channel_title}\n"
        f"\n"
        f"📝توضیحات کانال: {channel_desc}\n"
        f"\n"
        f"🆔@{channel}"
    )
    
    button = inline([
        [(f"👤 سفارش {members} ممبر", "noop")],
        [("💰 دریافت سکه", f"claim_coin:{order_id}")],
        [("📢 عضویت در کانال", f"https://t.me/{channel}")],
        [("🚫 گزارش", f"report:{order_id}")],
    ])
    
    try:
        post = await context.bot.send_message(
            f"@{Config.ADS_CHANNEL}",
            post_text,
            reply_markup=button
        )
    except Exception as e:
        with db.conn() as c:
            c.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        await context.bot.send_message(
            user_id,
            f"❌ خطا در ارسال پست: {e}",
            reply_markup=main_menu(is_admin(user_id))
        )
        set_user_state(user_id, "none")
        return
    
    with db.conn() as c:
        c.execute("UPDATE orders SET post_id = ? WHERE id = ?", (post.message_id, order_id))
    
    remove_coins(user_id, coins, "order_create", f"سفارش #{order_id}")
    update_user(user_id, orders_count=(get_user(user_id)["orders_count"] + 1))
    
    set_user_state(user_id, "none")
    
    post_link = f"https://t.me/{Config.ADS_CHANNEL}/{post.message_id}"
    
    success_text = (
        f"✅سفارش شما با موفقیت ثبت شد\n"
        f"\n"
        f"🔍 کد پیگیری سفارش شما {order_id} می باشد\n"
        f" \n"
        f"👥سفارش شما در قسمت پیگیری سفارشات قابل پیگیری است."
    )
    
    await context.bot.send_message(
        user_id,
        success_text,
        parse_mode="HTML",
        reply_markup=inline([
            [("🔍 مشاهده سفارش", post_link)],
        ])
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
    
    user = get_user(user_id)
    if not user:
        bot_username = (await context.bot.get_me()).username
        await q.answer(
            f"برای استفاده از کانال ابتدا ربات زیر را start کنید :\n@{bot_username}",
            show_alert=True
        )
        return
    
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
    
    coin = get_panel_join_coin(user["panel"])
    
    success = False
    with db.conn() as c:
        dup = c.execute(
            "SELECT 1 FROM order_members WHERE order_id = ? AND user_id = ?",
            (order_id, user_id)
        ).fetchone()
        if dup:
            await q.answer("❌ قبلاً ثبت شده.", show_alert=True)
            return
        
        cur = c.execute("""
            UPDATE orders SET member_received = member_received + 1
            WHERE id = ? AND member_received < member_target
        """, (order_id,))
        
        if cur.rowcount > 0:
            c.execute("""
                INSERT INTO order_members (order_id, user_id)
                VALUES (?, ?)
            """, (order_id, user_id))
            
            c.execute("UPDATE users SET ads_joined = ads_joined + 1 WHERE user_id = ?", (user_id,))
            success = True
    
    if not success:
        await q.answer("❌ ثبت نشد. دوباره تلاش کنید.", show_alert=True)
        return
    
    try:
        await check_referral_milestone(context, user_id)
    except Exception:
        pass
    
    add_coins(user_id, coin, "order_join", f"عضویت در سفارش #{order_id}")
    
    new_user = get_user(user_id)
    new_coins = new_user["coins"] if new_user else 0
    
    await q.answer(
        f"💰 سکه دریافتی : {coin} سکه | موجودی کل : {new_coins:,} سکه",
        show_alert=False
    )
    
    with db.conn() as c:
        o = c.execute(
            "SELECT member_received, member_target, post_id, admin_id, channel FROM orders WHERE id=?",
            (order_id,)
        ).fetchone()
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


# ==================== گزارش ====================
async def report_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    order_id = int(q.data.split(":")[1])
    
    user = get_user(user_id)
    if not user:
        bot_username = (await context.bot.get_me()).username
        await q.answer(
            f"برای استفاده از کانال ابتدا ربات زیر را start کنید :\n@{bot_username}",
            show_alert=True
        )
        return
    
    with db.conn() as c:
        if c.execute("SELECT 1 FROM order_reports WHERE order_id=? AND reporter_id=?", (order_id, user_id)).fetchone():
            await q.answer("❌ قبلاً گزارش داده‌اید.", show_alert=True)
            return
        
        o = c.execute(
            "SELECT id, admin_id, channel, post_id FROM orders WHERE id=?",
            (order_id,)
        ).fetchone()
        
        if not o:
            await q.answer("❌ سفارش یافت نشد.", show_alert=True)
            return
        
        c.execute(
            "INSERT INTO order_reports (order_id, reporter_id) VALUES (?, ?)",
            (order_id, user_id)
        )
    
    await q.answer("✅ گزارش شما ثبت شد.", show_alert=True)
    
    order_admin = o["admin_id"]
    channel = o["channel"]
    post_id = o["post_id"]
    
    text = (
        f"🚫 گزارش جدید\n"
        f"سفارش #{post_id}\n"
        f"گزارش‌دهنده: <code>{user_id}</code>\n"
        f"سفارش‌دهنده: <code>{order_admin}</code>\n"
        f"کانال: @{channel}"
    )
    
    post_link = f"https://t.me/{Config.ADS_CHANNEL}/{post_id}"
    
    keyboard = inline([
        [("👁 مشاهده پست", post_link)],
        [("👤 پروفایل گزارش‌دهنده", f"show_profile:{user_id}"),
         ("👤 پروفایل سفارش‌دهنده", f"show_profile:{order_admin}")],
        [("🗑 حذف گزارش", f"report_delete:{order_id}")],
    ])
    
    try:
        await context.bot.send_message(
            Config.ADMIN_ID,
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Report send error: {e}")


# ==================== نمایش پروفایل کاربر (برای ادمین) ====================
async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    admin_id = q.from_user.id
    
    if not is_admin(admin_id):
        await q.answer("❌ دسترسی ندارید.", show_alert=True)
        return
    
    await q.answer()
    
    target_id = int(q.data.split(":")[1])
    
    user = get_user(target_id)
    if not user:
        await q.message.reply_text("❌ کاربر در دیتابیس یافت نشد.")
        return
    
    from utils.texts import account_text
    text = account_text(user)
    
    await q.message.reply_text(
        text,
        parse_mode="HTML"
    )


# ==================== حذف گزارش ====================
async def report_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    
    if user_id != Config.ADMIN_ID:
        await q.answer("❌ فقط ادمین اصلی می‌تواند حذف کند.", show_alert=True)
        return
    
    order_id = int(q.data.split(":")[1])
    
    with db.conn() as c:
        c.execute("DELETE FROM order_reports WHERE order_id = ?", (order_id,))
    
    await q.answer("✅ گزارش حذف شد.", show_alert=True)
    
    try:
        await q.message.delete()
    except Exception:
        pass


# ==================== روتر callback ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    q = update.callback_query
    data = q.data
    
    if not (
        data.startswith("order_pick:") or
        data.startswith("order_confirm_yes:") or
        data == "order_confirm_no" or
        data.startswith("claim_coin:") or
        data.startswith("report:") or
        data.startswith("report_delete:") or
        data.startswith("show_profile:")
    ):
        return False
    
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
    if data.startswith("report_delete:"):
        await report_delete(update, context)
        return True
    if data.startswith("show_profile:"):
        await show_user_profile(update, context)
        return True
    if data.startswith("report:"):
        await report_order(update, context)
        return True
    return False
