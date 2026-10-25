"""Small ASGI middleware for request-body boundary enforcement."""

from starlette.responses import PlainTextResponse

MAX_REQUEST_BODY_BYTES = 25 * 1024 * 1024


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        if max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_lengths = [
            value for name, value in scope.get("headers", ()) if name.lower() == b"content-length"
        ]
        if content_lengths:
            if any(not value or not value.isdigit() for value in content_lengths):
                await PlainTextResponse("Invalid Content-Length", status_code=400)(scope, receive, send)
                return
            declared_lengths = {value.lstrip(b"0") or b"0" for value in content_lengths}
            if len(declared_lengths) != 1:
                await PlainTextResponse("Invalid Content-Length", status_code=400)(scope, receive, send)
                return
            declared_length = next(iter(declared_lengths))
            maximum_length = str(self.max_bytes).encode("ascii")
            if len(declared_length) > len(maximum_length) or (
                len(declared_length) == len(maximum_length) and declared_length > maximum_length
            ):
                await PlainTextResponse("Request body too large", status_code=413)(scope, receive, send)
                return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await PlainTextResponse("Request body too large", status_code=413)(scope, receive, send)
