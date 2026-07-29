import aiosqlite

DB_NAME = "referrals.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                referred_by INTEGER,
                score INTEGER DEFAULT 0,
                has_joined BOOLEAN DEFAULT 0
            )
        ''')
        await db.commit()

async def add_user(user_id: int, first_name: str, last_name: str, referred_by: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, first_name, last_name, referred_by) VALUES (?, ?, ?, ?)",
            (user_id, first_name, last_name, referred_by)
        )
        await db.commit()


async def process_subscription(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        # Fetch the user's current status and their referrer
        cursor = await db.execute("SELECT has_joined, referred_by FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        
        # user[0] is has_joined, user[1] is referred_by
        if user and user[0] == 0: 
            # 1. Mark the user as joined
            await db.execute("UPDATE users SET has_joined = 1 WHERE user_id = ?", (user_id,))
            
            # 2. If they were referred by someone, give that person +1 point
            if user[1] is not None:
                await db.execute("UPDATE users SET score = score + 1 WHERE user_id = ?", (user[1],))
            
            await db.commit()
            return True # Indicates they just joined right now
        return False # Indicates they already joined previously