import os
import asyncio
import logging
from threading import Thread
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


def run_flask():
    """اجرای Flask توی thread جداگانه"""
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    # Flask توی thread جداگانه (daemon)
    Thread(target=run_flask, daemon=True).start()
    
    # ربات توی main thread
    logger.info("Importing main...")
    from main import main as run_bot
    logger.info("Starting bot...")
    run_bot()
