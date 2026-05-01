"""
Entry point for the IT Schedule Management Bot.
Run: python -m src.main
"""
import logging
import sys

from src.config import BOT_TOKEN
from src.database.db import init_db
from src.bot.handlers import build_application


logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Copy .env.example → .env and fill in your token.")
        sys.exit(1)

    logger.info("Initializing database…")
    init_db()
    logger.info("Database ready.")

    app = build_application(BOT_TOKEN)
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
