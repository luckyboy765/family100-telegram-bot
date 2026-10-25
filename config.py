import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Multi owner: pisah dengan spasi. Contoh: OWNER_ID=123456 789012
OWNER_IDS = set(
    int(x) for x in os.getenv("OWNER_ID", "0").replace(",", " ").split()
    if x.strip().isdigit()
)
OWNER_ID = next(iter(OWNER_IDS), 0)  # untuk backward compat
LOG_GROUP = int(os.getenv("LOG_GROUP", "0"))
