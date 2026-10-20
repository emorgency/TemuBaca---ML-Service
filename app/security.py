import hmac

from fastapi import Header, HTTPException, status

from app.config import settings


# =========================
# INTERNAL TOKEN (R-07)
# =========================

# Every /api/* route is server to server: the TemuBaca website sends this
# header (its RECOMMENDATION_API_KEY). /health stays open.
TOKEN_HEADER = "X-Internal-Token"

# Recommendation requests are at most ~1.2 KB (20 interests of 50 chars).
MAX_API_BODY_BYTES = 8 * 1024


def require_internal_token(
    x_internal_token: str | None = Header(default=None, include_in_schema=False)
):
    expected = settings.internal_token

    # Fail closed: an unconfigured service never serves /api/*.
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal token is not configured."
        )

    if not x_internal_token or not hmac.compare_digest(
        x_internal_token.encode(),
        expected.encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized."
        )


# =========================
# BODY SIZE LIMIT
# =========================

class ApiBodyLimitMiddleware:
    """Reject /api/* bodies larger than MAX_API_BODY_BYTES with 413.

    Checks Content-Length first, then counts the streamed bytes, so a
    missing or false header cannot get a larger body through.
    """

    def __init__(self, app, max_bytes=MAX_API_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    too_large = int(value) > self.max_bytes
                except ValueError:
                    too_large = True
                if too_large:
                    await self._reject(send)
                    return

        # Read the whole (small) body up front so a short limit is enforced
        # before the app sees any of it.
        chunks = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                await self._reject(send)
                return
            chunks.append(chunk)
            more = message.get("more_body", False)

        body = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, send):
        payload = b'{"detail":"Request body too large."}'
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": payload})
