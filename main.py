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


async def handle_ping(reader, writer):
    """Responds with HTTP 200 OK for Render / UptimeRobot health check pings (supporting both HEAD and GET)."""
    try:
        # Read the request line (e.g., "HEAD / HTTP/1.1" or "GET / HTTP/1.1")
        request_line = await reader.readline()
        request_str = request_line.decode("utf-8")
        
        is_head = request_str.startswith("HEAD")
        
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            "Content-Length: 12\r\n"
            "Connection: close\r\n\r\n"
        )
        
        if is_head:
            # HEAD requests expect headers only, no response body
            writer.write(headers.encode("utf-8"))
        else:
            response = headers + "Bot is alive"
            writer.write(response.encode("utf-8"))
            
        await writer.drain()
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def start_health_check_server():
    """Starts a lightweight HTTP server on the PORT env variable for Render compatibility."""
    import os
    port_str = os.environ.get("PORT")
    if not port_str:
        logger.info("PORT environment variable not set. Skipping health check server.")
        return
        
    try:
        port = int(port_str)
        server = await asyncio.start_server(handle_ping, "0.0.0.0", port)
        logger.info(f"Health check server listening on 0.0.0.0:{port}")
        async with server:
            await server.serve_forever()
    except Exception as e:
        logger.error(f"Error starting health check server on port {port_str}: {e}")


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

    # 4. Start health check server (Render Free Web Service port binding)
    asyncio.create_task(start_health_check_server())

    # 5. Start polling
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
