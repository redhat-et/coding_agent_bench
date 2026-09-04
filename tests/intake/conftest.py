import socket

import pytest


@pytest.fixture(autouse=True)
def configure_server_url_validation(monkeypatch: pytest.MonkeyPatch):
    """Use a public test address without making network DNS calls."""
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )
