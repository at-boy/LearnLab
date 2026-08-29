from __future__ import annotations

import json
import threading
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    body: str
    authorization: str | None


@dataclass(frozen=True)
class QueuedResponse:
    status: int
    payload: object


class RequestLog:
    def __init__(self) -> None:
        self._requests: list[RecordedRequest] = []
        self._lock = threading.Lock()

    def append(self, request: RecordedRequest) -> None:
        with self._lock:
            self._requests.append(request)

    def one(self) -> RecordedRequest:
        with self._lock:
            assert len(self._requests) == 1
            return self._requests[0]

    def last(self) -> RecordedRequest:
        with self._lock:
            return self._requests[-1]

    def all(self) -> list[RecordedRequest]:
        with self._lock:
            return list(self._requests)


class FakeProxmoxServer:
    def __init__(self) -> None:
        self.requests = RequestLog()
        self._responses: deque[QueuedResponse] = deque()
        self._always: QueuedResponse | None = None
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join()
        self._server.server_close()

    def queue(self, status: int, payload: object) -> None:
        with self._lock:
            self._responses.append(QueuedResponse(status, payload))

    def always(self, status: int, payload: object) -> None:
        with self._lock:
            self._always = QueuedResponse(status, payload)

    def _next_response(self) -> QueuedResponse:
        with self._lock:
            if self._responses:
                return self._responses.popleft()
            if self._always is not None:
                return self._always
        raise AssertionError("Fake Proxmox server received an unqueued request")

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self._record_and_respond()

            def do_POST(self) -> None:  # noqa: N802
                self._record_and_respond()

            def do_PUT(self) -> None:  # noqa: N802
                self._record_and_respond()

            def do_DELETE(self) -> None:  # noqa: N802
                self._record_and_respond()

            def log_message(self, format: str, *args: object) -> None:
                return

            def _record_and_respond(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                server.requests.append(
                    RecordedRequest(
                        method=self.command,
                        path=self.path,
                        body=body,
                        authorization=self.headers.get("Authorization"),
                    )
                )
                response = server._next_response()
                encoded = json.dumps(response.payload).encode("utf-8")
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler


@contextmanager
def fake_proxmox_server() -> Iterator[FakeProxmoxServer]:
    server = FakeProxmoxServer()
    server.start()
    try:
        yield server
    finally:
        server.close()
