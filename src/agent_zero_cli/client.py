"""A0Client — communicates with Agent Zero via the /connector plugin namespace.

Auth flow:
  1. POST /login with username/password → session cookie
  2. Connect to /connector WS with session cookie (no CSRF needed)
  3. Send hello → subscribe_context → send_message
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable

import httpx
import socketio


# Connector plugin API base path
_PLUGIN_API = "/api/plugins/a0_connector/v1"


class A0Client:
    """Client for communicating with a running Agent Zero instance."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self.sio = socketio.AsyncClient()
        self.connected = False
        self.authenticated = False

        # Callbacks
        self.on_connect: Callable[[], None] | None = None
        self.on_disconnect: Callable[[], None] | None = None
        self.on_context_event: Callable[[dict[str, Any]], None] | None = None
        self.on_context_snapshot: Callable[[dict[str, Any]], None] | None = None
        self.on_context_complete: Callable[[dict[str, Any]], None] | None = None
        self.on_message_accepted: Callable[[dict[str, Any]], None] | None = None
        self.on_error: Callable[[dict[str, Any]], None] | None = None
        self.on_file_op: Callable[[dict[str, Any]], Any] | None = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _api_url(self, endpoint: str) -> str:
        return f"{self.base_url}{_PLUGIN_API}/{endpoint}"

    # ------------------------------------------------------------------
    # Health & auth
    # ------------------------------------------------------------------

    async def check_health(self) -> bool:
        """Check if the A0 instance is reachable.

        Uses the connector plugin capabilities endpoint (public, POST, no auth).
        Falls back to checking if the root URL responds.
        """
        try:
            response = await self.http.post(
                self._api_url("capabilities"),
                json={},
                timeout=5.0,
            )
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
        except Exception:
            # Fallback: just check if server responds at all
            try:
                response = await self.http.get(
                    self._url("/"), timeout=5.0, follow_redirects=False
                )
                return response.status_code in {200, 302}
            except Exception:
                return False

    async def needs_auth(self) -> bool:
        """Check if the instance requires authentication.

        Tries the connector plugin's protected chats_list endpoint (POST).
        A 302 redirect or 401/403 means auth is required.
        A 200 means already authenticated or no auth configured.
        """
        try:
            response = await self.http.post(
                self._api_url("chats_list"),
                json={},
                follow_redirects=False,
            )
            if response.status_code == 200:
                return False  # Already authenticated or no auth required
            if response.status_code in {302, 401, 403}:
                return True
        except Exception:
            pass

        # Fallback: check if root URL redirects to /login
        try:
            response = await self.http.get(
                self._url("/"), follow_redirects=False
            )
            if response.status_code == 302:
                location = response.headers.get("location", "")
                if "/login" in location:
                    return True
            return response.status_code in {401, 403}
        except Exception:
            return True

    async def login(self, username: str, password: str) -> bool:
        """Login with username/password. Session cookie is stored automatically."""
        response = await self.http.post(
            self._url("/login"),
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        if response.status_code in {200, 302}:
            self.authenticated = bool(self.http.cookies)
            return self.authenticated
        return False

    # ------------------------------------------------------------------
    # Cookie helpers
    # ------------------------------------------------------------------

    def _build_cookie_header(self) -> str:
        """Build Cookie header from session cookies (no CSRF needed)."""
        parts: list[str] = []
        for cookie in self.http.cookies.jar:
            parts.append(f"{cookie.name}={cookie.value}")
        return "; ".join(parts)

    # ------------------------------------------------------------------
    # WebSocket — /connector namespace
    # ------------------------------------------------------------------

    async def connect_websocket(self) -> None:
        """Connect to the /connector WebSocket namespace with session cookies."""
        headers: dict[str, str] = {
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        }
        cookie_header = self._build_cookie_header()
        if cookie_header:
            headers["Cookie"] = cookie_header

        # Register event handlers
        ns = "/connector"

        @self.sio.on("connect", namespace=ns)
        async def _on_connect() -> None:
            self.connected = True
            cb = self.on_connect
            if cb is not None:
                cb()

        @self.sio.on("disconnect", namespace=ns)
        async def _on_disconnect() -> None:
            self.connected = False
            cb = self.on_disconnect
            if cb is not None:
                cb()

        @self.sio.on("hello_ok", namespace=ns)
        async def _on_hello_ok(data: dict[str, Any]) -> None:
            pass  # Protocol handshake ack

        @self.sio.on("context_snapshot", namespace=ns)
        async def _on_context_snapshot(data: dict[str, Any]) -> None:
            cb = self.on_context_snapshot
            if cb is not None:
                cb(data)

        @self.sio.on("context_event", namespace=ns)
        async def _on_context_event(data: dict[str, Any]) -> None:
            cb = self.on_context_event
            if cb is not None:
                cb(data)

        @self.sio.on("context_complete", namespace=ns)
        async def _on_context_complete(data: dict[str, Any]) -> None:
            cb = self.on_context_complete
            if cb is not None:
                cb(data)

        @self.sio.on("message_accepted", namespace=ns)
        async def _on_message_accepted(data: dict[str, Any]) -> None:
            cb = self.on_message_accepted
            if cb is not None:
                cb(data)

        @self.sio.on("error", namespace=ns)
        async def _on_error(data: dict[str, Any]) -> None:
            cb = self.on_error
            if cb is not None:
                cb(data)

        @self.sio.on("file_op", namespace=ns)
        async def _on_file_op(data: dict[str, Any]) -> dict[str, Any]:
            """Handle file operation requests from text_editor_remote."""
            cb = self.on_file_op
            if cb is not None:
                result = cb(data)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            return {"op_id": data.get("op_id"), "ok": False, "error": "No file_op handler"}

        await self.sio.connect(
            self.base_url,
            namespaces=[ns],
            headers=headers,
            transports=["websocket"],
        )

    async def send_hello(self) -> None:
        """Send protocol hello to the /connector namespace."""
        await self.sio.emit(
            "hello",
            {
                "protocol": "a0-connector.v1",
                "client": "agent-zero-cli",
                "client_version": "0.1.0",
            },
            namespace="/connector",
        )

    async def subscribe_context(self, context_id: str, from_seq: int = 0) -> None:
        """Subscribe to events from a context."""
        await self.sio.emit(
            "subscribe_context",
            {"context_id": context_id, "from": from_seq},
            namespace="/connector",
        )

    async def unsubscribe_context(self, context_id: str) -> None:
        """Unsubscribe from a context's events."""
        await self.sio.emit(
            "unsubscribe_context",
            {"context_id": context_id},
            namespace="/connector",
        )

    async def send_message(self, text: str, context_id: str) -> None:
        """Send a chat message to a context via the /connector WS."""
        await self.sio.emit(
            "send_message",
            {
                "context_id": context_id,
                "message": text,
                "client_message_id": str(uuid.uuid4()),
            },
            namespace="/connector",
        )

    # ------------------------------------------------------------------
    # REST API — chat management
    # ------------------------------------------------------------------

    async def create_chat(self) -> str:
        """Create a new chat context via the connector API."""
        response = await self.http.post(
            self._api_url("chat_create"), json={}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("context_id") or data.get("ctxid", "")

    async def list_chats(self) -> list[dict[str, Any]]:
        """List all active chat contexts."""
        response = await self.http.post(
            self._api_url("chats_list"), json={}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("contexts", data.get("chats", []))

    async def remove_chat(self, context_id: str) -> None:
        """Delete a chat context."""
        response = await self.http.post(
            self._api_url("chat_delete"),
            json={"context_id": context_id},
        )
        response.raise_for_status()

    async def list_projects(self) -> list[dict[str, Any]]:
        """List available projects."""
        response = await self.http.post(
            self._api_url("projects_list"), json={}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("projects", [])

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def disconnect(self) -> None:
        if self.sio.connected:
            await self.sio.disconnect()
        await self.http.aclose()
