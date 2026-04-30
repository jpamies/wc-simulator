"""Tournament authentication helpers.

Each tournament has a manage_token_hash. To write to a tournament, the caller
must send the raw token in the X-Manage-Token header. We compare the SHA-256
hash of the supplied token against the stored hash.

The canonical tournament's token is the WCS_ADMIN_KEY env var.
"""

import hashlib
import secrets
import string

from fastapi import HTTPException, Query, Request

from src.backend.database import get_db
from src.backend.config import ADMIN_KEY

# Default tournament_id (canonical)
CANONICAL_ID = 1


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_slug(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_manage_token() -> str:
    return secrets.token_urlsafe(32)


async def get_tournament_id(request: Request, tournament_id: int | None = Query(None)) -> int:
    """Dependency: resolve tournament_id from query param, defaulting to canonical."""
    return tournament_id if tournament_id is not None else CANONICAL_ID


async def require_tournament_write(request: Request, tournament_id: int) -> None:
    """Verify the caller has write access to the tournament.
    
    Checks X-Manage-Token header against the tournament's stored hash.
    Raises 403 if unauthorized.
    """
    token = request.headers.get("X-Manage-Token", "")
    if not token:
        raise HTTPException(403, "X-Manage-Token header required for write operations")

    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT manage_token_hash, is_canonical FROM tournaments WHERE id = $1",
            (tournament_id,),
        )
        if not row:
            raise HTTPException(404, "Tournament not found")

        stored_hash = row[0]["manage_token_hash"]
        if hash_token(token) != stored_hash:
            raise HTTPException(403, "Invalid manage token")
    finally:
        await db.close()
