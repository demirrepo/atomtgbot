import os
import asyncpg

pool = None

async def init_db():
    global pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    pool = await asyncpg.create_pool(DATABASE_URL, statement_cache_size=0)
    
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                referred_by BIGINT,
                score INTEGER DEFAULT 0,
                has_joined BOOLEAN DEFAULT FALSE
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        await conn.execute('''
            INSERT INTO settings (id, is_active) 
            VALUES (1, TRUE) 
            ON CONFLICT (id) DO NOTHING
        ''')

async def add_user(user_id: int, first_name: str, last_name: str, referred_by: int = None):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, first_name, last_name, referred_by) 
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO NOTHING
        ''', user_id, first_name, last_name, referred_by)

async def set_user_joined_status(user_id: int, status: bool):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET has_joined = $1 WHERE user_id = $2", status, user_id)

async def get_user_status(user_id: int):
    async with pool.acquire() as conn:
        status = await conn.fetchval("SELECT has_joined FROM users WHERE user_id = $1", user_id)
        return bool(status) if status is not None else False

async def get_total_users_count():
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        return count if count else 0

async def get_all_user_ids():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [row['user_id'] for row in rows]


# --------------------------------------------------
# LEFTOVER FROM AN EARLIER CONTEST VERSION
# Not used by any current handler — safe to ignore
# --------------------------------------------------

async def process_subscription(user_id: int):
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT has_joined, referred_by FROM users WHERE user_id = $1", user_id)
        if user and user['has_joined'] == False:
            await conn.execute("UPDATE users SET has_joined = TRUE WHERE user_id = $1", user_id)
            if user['referred_by'] is not None:
                await conn.execute("UPDATE users SET score = score + 1 WHERE user_id = $1", user['referred_by'])
            return True
        return False

async def get_top_users(limit: int = 10):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT first_name, score FROM users WHERE score > 0 ORDER BY score DESC LIMIT $1", limit)
        return [(row['first_name'], row['score']) for row in rows]

async def get_user_score(user_id: int):
    async with pool.acquire() as conn:
        score = await conn.fetchval("SELECT score FROM users WHERE user_id = $1", user_id)
        return score if score else 0

async def get_contest_status():
    async with pool.acquire() as conn:
        status = await conn.fetchval("SELECT is_active FROM settings WHERE id = 1")
        return bool(status) if status is not None else True

async def toggle_contest_status():
    async with pool.acquire() as conn:
        current = await conn.fetchval("SELECT is_active FROM settings WHERE id = 1")
        new_status = False if current else True
        await conn.execute("UPDATE settings SET is_active = $1 WHERE id = 1", new_status)
        return new_status

async def get_all_results():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, first_name, last_name, score FROM users ORDER BY score DESC")
        return [(row['user_id'], row['first_name'], row['last_name'], row['score']) for row in rows]

async def reset_database():
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await conn.execute("UPDATE settings SET is_active = FALSE WHERE id = 1")