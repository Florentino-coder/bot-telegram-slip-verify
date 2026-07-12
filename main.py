import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from handlers import start, slip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("SlipBot")


async def main():
    logger.info("Starting Telegram Slip Verification Bot...")

    # 1. Validate environment configuration
    missing_configs = Config.validate()
    if missing_configs:
        logger.error(
            f"❌ Critical Configuration Error: The following environment variables are missing:\n"
            f"   {', '.join(missing_configs)}\n"
            f"Please check your .env file or host environment settings. Exiting."
        )
        sys.exit(1)

    # 2. Initialize Bot and Dispatcher
    try:
        # Defaults to HTML/Markdown parse mode configuration where needed
        bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Telegram Bot client: {e}")
        sys.exit(1)

    # 3. Include Handler Routers
    dp.include_router(start.router)
    dp.include_router(slip.router)

    # 4. Start polling
    logger.info("Bot router mapping registered. Running start_polling...")
    try:
        # Delete webhook before starting polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Bot execution halted due to unexpected exception: {e}")
    finally:
        # Close bot session cleanly
        await bot.session.close()
        logger.info("Bot session closed successfully. Process terminated.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user keyboard interrupt.")
        sys.exit(0)
