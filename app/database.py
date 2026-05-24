import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

import bcrypt

pool = None

async def init_db_pool():
    global pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable not set")
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return pool

async def get_pool():
    global pool
    if pool is None:
        await init_db_pool()
    return pool

async def create_tenant_schema(schema_name: str, admin_username: str, admin_password: str):
    global pool
    if pool is None:
        await init_db_pool()
    async with pool.acquire() as conn:
        safe_schema = schema_name.replace('"', '').replace("'", "")
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{safe_schema}"')
        await conn.execute(f'SET search_path TO "{safe_schema}"')
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                sku TEXT UNIQUE NOT NULL,
                barcode TEXT UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                student_class TEXT,
                subject TEXT,
                purchase_price REAL NOT NULL,
                selling_price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                tag TEXT,
                variation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sales (
                id SERIAL PRIMARY KEY,
                receipt_number TEXT NOT NULL UNIQUE,
                student_name TEXT NOT NULL,
                father_name TEXT NOT NULL,
                cnic TEXT,
                student_class TEXT NOT NULL,
                phone_no TEXT NOT NULL,
                address TEXT,
                sale_type TEXT NOT NULL,
                total_amount REAL NOT NULL,
                cash_paid REAL DEFAULT 0.0,
                profit REAL DEFAULT 0.0,
                payment_status TEXT DEFAULT 'Paid',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sale_items (
                id SERIAL PRIMARY KEY,
                sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                sku TEXT NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL
            );
        """)
        await conn.execute("""
            INSERT INTO users (username, password) VALUES ($1, $2)
            ON CONFLICT (username) DO NOTHING;
        """, admin_username, admin_password)
        await conn.execute('SET search_path TO public')

async def tenant_exists(subdomain: str) -> bool:
    global pool
    if pool is None:
        await init_db_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT 1 FROM public.schools WHERE subdomain = $1", subdomain) is not None
