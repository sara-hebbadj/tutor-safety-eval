import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never reach the internet or need an API key."""

    def blocked(*args, **kwargs):
        raise RuntimeError("network access is blocked in tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
