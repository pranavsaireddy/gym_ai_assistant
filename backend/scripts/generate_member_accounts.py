# backend/scripts/generate_member_accounts.py
"""
Generates chatbot username + password for every member who doesn't have one yet.
Run once after Phase 2 is deployed.

Usage:
    cd D:\\aigym\\gym-ai\\backend
    venv\\Scripts\\activate
    python scripts/generate_member_accounts.py

Output:
    Prints credentials to console AND saves to credentials.txt
    Share credentials with each member (WhatsApp/SMS) before Phase 3 launch.

IMPORTANT:
    credentials.txt contains plain-text passwords — delete it after distributing.
    Never commit credentials.txt to git.
"""
import asyncio
import secrets
import string
from datetime import datetime
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import select

# Add project root to path so imports work
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.database import AsyncSessionLocal, Member

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def make_username(name: str, member_id: str) -> str:
    """
    Generate a username from member name + last 4 digits of Yoactiv ID.
    Example: "Pranav Sai Reddy" + "2587500" → "pranavsai7500"
    """
    # Take first 8 chars of name (letters only, lowercase)
    clean = "".join(c for c in name.lower() if c.isalpha())[:8]
    suffix = member_id[-4:]
    return f"{clean}{suffix}"


def make_password(length: int = 8) -> str:
    """
    Generate a random 8-character password.
    Mix of letters and digits — easy to type, hard to guess.
    Avoids ambiguous characters (0, O, l, 1) for readability.
    """
    chars = (
        "abcdefghjkmnpqrstuvwxyz"   # lowercase, no ambiguous
        "ABCDEFGHJKMNPQRSTUVWXYZ"   # uppercase, no ambiguous
        "23456789"                   # digits, no ambiguous
    )
    return "".join(secrets.choice(chars) for _ in range(length))


async def generate_all():
    async with AsyncSessionLocal() as db:
        # Only process members who don't have a chatbot account yet
        result = await db.execute(
            select(Member).where(Member.chatbot_username == None)
        )
        members = result.scalars().all()

        if not members:
            print("All members already have chatbot accounts. Nothing to do.")
            return

        print(f"Generating accounts for {len(members)} members...")
        print()

        credentials = []

        for m in members:
            username = make_username(m.name, m.yoactiv_member_id)
            password = make_password()

            # Check for username collision (unlikely but handle it)
            existing = await db.execute(
                select(Member).where(Member.chatbot_username == username)
            )
            if existing.scalar_one_or_none():
                # Append extra digits to make unique
                username = f"{username}{secrets.randbelow(99):02d}"

            m.chatbot_username = username
            m.chatbot_password_hash = pwd_ctx.hash(password)
            credentials.append((m.name, m.phone, username, password))

        await db.commit()
        print(f"✅ Generated {len(credentials)} accounts. Saved to database.\n")

        # Print to console
        print(f"{'NAME':<30} {'PHONE':<15} {'USERNAME':<20} {'PASSWORD':<12}")
        print("-" * 80)
        for name, phone, uname, pwd in credentials:
            print(f"{name:<30} {phone:<15} {uname:<20} {pwd:<12}")

        # Save to file
        output_path = Path(__file__).parent / "credentials.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"Member Chatbot Credentials — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"Muscletech Fitness, Bandlaguda Jagir\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"{'NAME':<30} {'PHONE':<15} {'USERNAME':<20} {'PASSWORD':<12}\n")
            f.write("-" * 80 + "\n")
            for name, phone, uname, pwd in credentials:
                f.write(f"{name:<30} {phone:<15} {uname:<20} {pwd:<12}\n")
            f.write("\n⚠️  Delete this file after distributing credentials to members.\n")

        print(f"\n✅ Saved to: {output_path}")
        print("⚠️  Delete credentials.txt after distributing to members.")
        print("⚠️  Never commit credentials.txt to git.")


if __name__ == "__main__":
    asyncio.run(generate_all())
