import asyncio

from fastapi.testclient import TestClient

from backend.app.middleware import MAX_REQUEST_BODY_BYTES, RequestBodyLimitMiddleware


class EchoBodyApp:
    def __init__(self):
        self.called = False
        self.body = bytearray()

    async def __call__(self, scope, receive, send):
        self.called = True
        if scope["type"] != "http":
            await send({"type": "lifespan.test"})
            return

        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            self.body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break

        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": bytes(self.body)})


def invoke(app, scope, messages):
    sent = []

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def http_scope(headers=()):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "root_path": "",
        "headers": list(headers),
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }


def test_rejects_oversized_content_length_before_reading_body():
    app = EchoBodyApp()
    received = False

    async def receive():
        nonlocal received
        received = True
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(
        RequestBodyLimitMiddleware(app, max_bytes=4)(
            http_scope([(b"content-length", b"5")]), receive, send
        )
    )

    assert sent[0]["status"] == 413
    assert not received
    assert not app.called


def test_rejects_malformed_content_length():
    app = EchoBodyApp()
    sent = invoke(
        RequestBodyLimitMiddleware(app, max_bytes=4),
        http_scope([(b"content-length", b"four")]),
        [],
    )

    assert sent[0]["status"] == 400
    assert not app.called


def test_rejects_very_long_numeric_content_length_without_integer_conversion_error():
    app = EchoBodyApp()
    sent = invoke(
        RequestBodyLimitMiddleware(app, max_bytes=4),
        http_scope([(b"content-length", b"9" * 5000)]),
        [],
    )

    assert sent[0]["status"] == 413
    assert not app.called


def test_rejects_streamed_body_that_exceeds_limit_across_chunks():
    app = EchoBodyApp()
    sent = invoke(
        RequestBodyLimitMiddleware(app, max_bytes=4),
        http_scope(),
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"de", "more_body": False},
        ],
    )

    assert sent[0]["status"] == 413
    assert app.body == b"abc"


def test_accepts_body_at_exact_limit():
    app = EchoBodyApp()
    sent = invoke(
        RequestBodyLimitMiddleware(app, max_bytes=4),
        http_scope([(b"content-length", b"4")]),
        [{"type": "http.request", "body": b"abcd", "more_body": False}],
    )

    assert sent[0]["status"] == 200
    assert sent[1]["body"] == b"abcd"


def test_passes_non_http_asgi_scopes_through_unchanged():
    app = EchoBodyApp()
    sent = invoke(
        RequestBodyLimitMiddleware(app, max_bytes=4),
        {"type": "lifespan", "asgi": {"version": "3.0"}},
        [],
    )

    assert app.called
    assert sent == [{"type": "lifespan.test"}]


def test_global_request_limit_matches_the_proxy_25_mib_cap():
    assert MAX_REQUEST_BODY_BYTES == 25 * 1024 * 1024


def test_application_applies_body_limit_and_security_headers():
    from backend.app.main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/",
            content=b"",
            headers={"content-length": str(MAX_REQUEST_BODY_BYTES + 1)},
        )

    assert response.status_code == 413
    assert response.headers.get("content-security-policy")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
