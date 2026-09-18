import os
import threading
import logging
from flask import Flask

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def health():
    return {"status": "ok", "service": "telegram-bot"}


def run_telegram():
    try:
        logger.info("Importing main...")
        from main import main as run_bot
        logger.info("Starting bot...")
        run_bot()
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")


if __name__ == "__main__":
    # ربات توی thread جداگانه
    threading.Thread(target=run_telegram, daemon=True).start()
    
    # Flask روی پورت Render
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)
