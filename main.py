import asyncio
from aiogram import Bot, Dispatcher
from database import init_db
from handlers import router 

BOT_TOKEN = "8954403531:AAHGlWIVI6Qx0Eprd4IKqefIYp-ULKmihp0" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    print("Initializing database...")
    await init_db()
    
    # Include the router so the bot knows how to answer /start
    dp.include_router(router) 
    
    print("Bot is awake and polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())