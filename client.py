import json
import socket
import struct
from typing import Any

import config


class CppClient:
    """Python client for the C++ VectorDB server.

    Uses length-prefixed framing (4-byte big-endian uint32 + JSON payload)
    over a TCP socket to communicate with the server.
    """

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or config.CPP_SERVER_HOST
        self.port = port or config.CPP_SERVER_PORT

    def connect(self) -> bool:
        """Verify the C++ server is reachable (probe connection, then close).

        The server handles one request per connection, so we don't keep
        a persistent socket. Each store/search call opens its own connection.
        """
        if not self.is_alive():
            print(f"  [ERROR] Cannot connect to cpp_server at {self.host}:{self.port}")
            print(f"  Start it first: ./cpp_server/build/vectordb_server")
            return False
        return True

    def close(self):
        """No-op. Connections are per-request; kept for interface compatibility."""
        pass

    def is_alive(self) -> bool:
        """Check if the server is reachable by opening a fresh connection."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((self.host, self.port))
            sock.close()
            return True
        except (ConnectionRefusedError, OSError):
            return False

    def store_chunk(
        self,
        chunk_id: str,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """Send a store request to the C++ server.

        Returns the server response dict (e.g. {"status": "ok"}).
        """
        request = {
            "action": "store",
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "text": text,
            "metadata": metadata or {},
        }
        return self._send_request(request)

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_id: str = "",
    ) -> list[dict]:
        """Send a search request to the C++ server.

        Returns a list of result dicts, each with chunk_id, score, and text.
        """
        request: dict[str, Any] = {
            "action": "search",
            "query": query,
            "top_k": top_k,
        }
        if doc_id:
            request["doc_id"] = doc_id

        response = self._send_request(request)
        return response.get("results", [])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_request(self, request: dict) -> dict:
        """Open a connection, send one request, read the response, close."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        try:
            sock.connect((self.host, self.port))
            payload = json.dumps(request).encode("utf-8")

            # Write: 4-byte big-endian length + payload
            sock.sendall(struct.pack("!I", len(payload)) + payload)

            # Read: 4-byte big-endian length header
            length_buf = self._recv_exact(sock, 4)
            length = struct.unpack("!I", length_buf)[0]

            # Read: payload
            response_buf = self._recv_exact(sock, length)
            response = json.loads(response_buf.decode("utf-8"))

            if response.get("status") == "error":
                raise RuntimeError(f"Server error: {response.get('message', 'unknown')}")

            return response
        finally:
            sock.close()

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes:
        """Read exactly n bytes from the socket."""
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed while reading response")
            buf.extend(chunk)
        return bytes(buf)
