import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiohttp import web
from database import init_db
from handlers import router 

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN") 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DUMMY WEB SERVER LOGIC ---
async def handle_ping(request):
    # This is what UptimeRobot will see when it visits your Render URL
    return web.Response(text="Bot is awake and running!")

async def run_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render assigns a dynamic PORT via environment variables
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Dummy web server started on port {port}")
# ------------------------------

async def main():
    print("Database ishga tushmoqda...")
    await init_db()
    
    dp.include_router(router) 
    
    # 1. Start the dummy web server in the background
    asyncio.create_task(run_dummy_server())
    
    # 2. Start the Telegram bot
    print("Bot ishlamoqda...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    asyncio.run(main())