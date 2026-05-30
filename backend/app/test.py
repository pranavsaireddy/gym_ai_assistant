import asyncio
import asyncpg

DB_URL = "postgresql+asyncpg://postgres:Pranavsai%40123@db.ydzztgiiyfzmsbsudnfl.supabase.co:5432/postgres"

async def test_db():
    try:
        conn = await asyncpg.connect(
            DB_URL.replace("+asyncpg", ""),  # asyncpg needs pure URL
            ssl="require"
        )
        
        result = await conn.fetch("SELECT 1;")
        print("✅ Connected:", result)

        await conn.close()

    except Exception as e:
        print("❌ Connection Failed:", e)

asyncio.run(test_db())