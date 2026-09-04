import os
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]


async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.workspaces.create_index("slug", unique=True)
    await db.collections.create_index("slug", unique=True)
    await db.collections.create_index("workspace_id")
    await db.testimonials.create_index("workspace_id")
    await db.testimonials.create_index("collection_id")
    await db.widgets.create_index("workspace_id")
    await db.analytics_events.create_index("workspace_id")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")
