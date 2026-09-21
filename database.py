import sqlite3
from contextlib import contextmanager
from config import Config

class Database:
    def __init__(self, path=None):
        self.path = path or Config.DB_PATH
        self._init_db()
    
    @contextmanager
    def conn(self):
        """Context manager برای اتصال امن به دیتابیس"""
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    
    def _init_db(self):
        """ساخت جداول در اولین اجرا"""
        with self.conn() as c:
            # === کاربران ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id         INTEGER PRIMARY KEY,
                    first_name      TEXT,
                    username        TEXT,
                    phone           TEXT,
                    coins           INTEGER DEFAULT 10,
                    panel           TEXT DEFAULT 'عادی',
                    panel_days      INTEGER DEFAULT 0,
                    panel_start     DATE,
                    warnings        INTEGER DEFAULT 0,
                    banned          INTEGER DEFAULT 0,
                    referrer_id     INTEGER,
                    join_date       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_daily      INTEGER DEFAULT 0,
                    ads_joined      INTEGER DEFAULT 0,
                    orders_count    INTEGER DEFAULT 0,
                    received_coins  INTEGER DEFAULT 0,
                    sent_coins      INTEGER DEFAULT 0,
                    state           TEXT DEFAULT 'none',
                    state_data      TEXT,
                    total_earned    INTEGER DEFAULT 0,
                    total_spent     INTEGER DEFAULT 0,
                    today_earned    INTEGER DEFAULT 0,
                    today_date      TEXT,
                    referral_today  INTEGER DEFAULT 0,
                    referral_rewarded INTEGER DEFAULT 0,
                    send_coin_admin INTEGER DEFAULT 0,
                    last_hourly     INTEGER DEFAULT 0,
                    hourly_earned   INTEGER DEFAULT 0
                )
            """)
            
            # === اضافه کردن ستون‌های جدید به دیتابیس موجود ===
            existing_columns = [row[1] for row in c.execute("PRAGMA table_info(users)").fetchall()]
            new_columns = {
                "total_earned": "INTEGER DEFAULT 0",
                "total_spent": "INTEGER DEFAULT 0",
                "today_earned": "INTEGER DEFAULT 0",
                "today_date": "TEXT",
                "referral_today": "INTEGER DEFAULT 0",
                "referral_rewarded": "INTEGER DEFAULT 0",
                "send_coin_admin": "INTEGER DEFAULT 0",
                "last_hourly": "INTEGER DEFAULT 0",
                "hourly_earned": "INTEGER DEFAULT 0",
            }
            for col, col_type in new_columns.items():
                if col not in existing_columns:
                    try:
                        c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass
            
            # === سفارشات ممبر ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id        INTEGER NOT NULL,
                    channel         TEXT NOT NULL,
                    channel_id      INTEGER,
                    post_id         INTEGER,
                    member_target   INTEGER NOT NULL,
                    member_received INTEGER DEFAULT 0,
                    coins_cost      INTEGER NOT NULL,
                    status          TEXT DEFAULT 'running',
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cancel_at       INTEGER,
                    FOREIGN KEY (admin_id) REFERENCES users(user_id)
                )
            """)
            
            # === اعضای سفارش ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS order_members (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id    INTEGER NOT NULL,
                    user_id     INTEGER NOT NULL,
                    joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    left_at     TIMESTAMP,
                    UNIQUE(order_id, user_id),
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
            
            # === گزارشات سفارش ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS order_reports (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id    INTEGER NOT NULL,
                    reporter_id INTEGER NOT NULL,
                    reason      TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(order_id, reporter_id)
                )
            """)
            
            # === تراکنش‌ها ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_id     INTEGER,
                    to_id       INTEGER,
                    amount      INTEGER NOT NULL,
                    type        TEXT NOT NULL,
                    description TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === کدهای هدیه ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS gift_codes (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    code                TEXT NOT NULL,
                    amount              INTEGER NOT NULL,
                    max_users           INTEGER DEFAULT 1,
                    used_count          INTEGER DEFAULT 0,
                    post_id             INTEGER,
                    post_success_id     INTEGER,
                    type                TEXT DEFAULT 'global',
                    target_user_id      INTEGER,
                    created_by          INTEGER,
                    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active           INTEGER DEFAULT 1
                )
            """)
            
            # === اضافه کردن ستون‌های جدید به gift_codes ===
            gift_cols = [r[1] for r in c.execute("PRAGMA table_info(gift_codes)").fetchall()]
            if "id" not in gift_cols:
                c.execute("DROP TABLE IF EXISTS gift_codes")
                c.execute("""
                    CREATE TABLE gift_codes (
                        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                        code                TEXT NOT NULL,
                        amount              INTEGER NOT NULL,
                        max_users           INTEGER DEFAULT 1,
                        used_count          INTEGER DEFAULT 0,
                        post_id             INTEGER,
                        post_success_id     INTEGER,
                        type                TEXT DEFAULT 'global',
                        target_user_id      INTEGER,
                        created_by          INTEGER,
                        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active           INTEGER DEFAULT 1
                    )
                """)
            
            # === دریافت‌کنندگان کد هدیه ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS gift_code_users (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_id     INTEGER NOT NULL,
                    user_id     INTEGER NOT NULL,
                    used_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code_id, user_id),
                    FOREIGN KEY (code_id) REFERENCES gift_codes(id)
                )
            """)
            
            # === تنظیمات فروشگاه ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_type   TEXT NOT NULL,
                    name        TEXT,
                    price       INTEGER,
                    coin_amount INTEGER,
                    panel_name  TEXT,
                    panel_days  INTEGER,
                    position    INTEGER
                )
            """)
            
            # === آیتم‌های سفارش ممبر ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    key         TEXT PRIMARY KEY,
                    name        TEXT,
                    members     INTEGER,
                    coins       INTEGER,
                    position    INTEGER
                )
            """)
            
            # === اضافه کردن پیش‌فرض‌های order_items ===
            default_items = [
                ("item_20",  "👤 20 ممبر",   20,  40,  1),
                ("item_10",  "👤 10 ممبر",   10,  20,  2),
                ("item_100", "👤 100 ممبر",  100, 200, 3),
                ("item_50",  "👤 50 ممبر",   50,  100, 4),
                ("item_400", "👤 400 ممبر",  400, 800, 5),
                ("item_200", "👤 200 ممبر",  200, 400, 6),
            ]
            for key, name, members, coins, pos in default_items:
                c.execute("""
                    INSERT OR IGNORE INTO order_items (key, name, members, coins, position)
                    VALUES (?, ?, ?, ?, ?)
                """, (key, name, members, coins, pos))
            
            # === متن‌ها و تنظیمات ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key         TEXT PRIMARY KEY,
                    value       TEXT
                )
            """)
            
            # === مدیران ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id     INTEGER PRIMARY KEY,
                    added_by    INTEGER,
                    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === کانال‌ها و گروه‌های ربات ===
            c.execute("""
                CREATE TABLE IF NOT EXISTS bot_chats (
                    chat_id     INTEGER PRIMARY KEY,
                    chat_type   TEXT,
                    title       TEXT,
                    username    TEXT,
                    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === ایندکس‌ها ===
            c.execute("CREATE INDEX IF NOT EXISTS idx_orders_admin ON orders(admin_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referrer_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_gift_code_id ON gift_code_users(code_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_gift_user_id ON gift_code_users(user_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_gift_active ON gift_codes(is_active)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_gift_type ON gift_codes(type)")
            
            # === ادمین اصلی ===
            c.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                (Config.ADMIN_ID,)
            )

db = Database()
