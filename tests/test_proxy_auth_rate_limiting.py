from pathlib import Path


def test_nginx_limits_auth_abuse_routes_by_socket_ip_and_returns_429():
    config = Path("nginx.conf").read_text(encoding="utf-8")
    location = (
        "location ~ ^/api/auth/"
        "(login|register|verify-email|resend-verification|forgot-password|reset-password)/?$ {"
    )

    assert "limit_req_zone $binary_remote_addr zone=auth_ip:10m rate=30r/m;" in config
    assert "limit_req_status 429;" in config
    assert location in config
    location_body = config.split(location, maxsplit=1)[1].split("\n        }", maxsplit=1)[0]
    assert "limit_req zone=auth_ip burst=10 nodelay;" in location_body
    assert "proxy_pass http://backend_app;" in location_body

    assert "real_ip_header" not in config
    assert "set_real_ip_from" not in config


def test_compose_relies_on_complete_edge_limit_and_direct_fastapi_keeps_its_default():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    auth_router = Path("backend/app/routers/auth.py").read_text(encoding="utf-8")

    assert "- APP_AUTH_IP_RATE_LIMIT_ENABLED=false" in compose
    assert '_MAX_PUBLIC_AUTH_ATTEMPTS = 30' in auth_router
    assert 'os.getenv("APP_AUTH_IP_RATE_LIMIT_ENABLED", "true")' in auth_router
