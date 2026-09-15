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
                    referral_today  INTEGER DEFAULT 0
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
                    code        TEXT PRIMARY KEY,
                    amount      INTEGER NOT NULL,
                    used_by     INTEGER,
                    used_at     TIMESTAMP,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            
            # === ایندکس‌ها ===
            c.execute("CREATE INDEX IF NOT EXISTS idx_orders_admin ON orders(admin_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referrer_id)")
            
            # === ادمین اصلی ===
            c.execute(
                "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
                (Config.ADMIN_ID,)
            )

db = Database()
