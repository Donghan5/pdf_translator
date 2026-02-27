"""Tests for client.py — CppClient socket communication."""

import json
import struct
from unittest.mock import MagicMock, patch

import pytest

from client import CppClient


def make_mock_socket(response_dict):
    """Create a mock socket that returns a length-prefixed JSON response."""
    payload = json.dumps(response_dict).encode("utf-8")
    length_header = struct.pack("!I", len(payload))
    full_response = length_header + payload

    sock = MagicMock()
    # recv returns the full data in one call for simplicity
    sock.recv.side_effect = [length_header, payload]
    return sock


# =============================================================================
# is_alive
# =============================================================================

class TestIsAlive:
    def test_success(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            client = CppClient()
            assert client.is_alive() is True
            mock_sock.connect.assert_called_once()
            mock_sock.close.assert_called_once()

    def test_connection_refused(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError
            mock_sock_cls.return_value = mock_sock
            client = CppClient()
            assert client.is_alive() is False

    def test_os_error(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = OSError("Network unreachable")
            mock_sock_cls.return_value = mock_sock
            client = CppClient()
            assert client.is_alive() is False


# =============================================================================
# connect
# =============================================================================

class TestConnect:
    def test_alive_returns_true(self):
        client = CppClient()
        with patch.object(client, "is_alive", return_value=True):
            assert client.connect() is True

    def test_dead_returns_false(self):
        client = CppClient()
        with patch.object(client, "is_alive", return_value=False):
            assert client.connect() is False


# =============================================================================
# store_chunk
# =============================================================================

class TestStoreChunk:
    def test_success(self):
        client = CppClient()
        response = {"status": "ok"}

        with patch.object(client, "_send_request", return_value=response) as mock_send:
            result = client.store_chunk("c1", "d1", "text", {"key": "val"})
        assert result == {"status": "ok"}
        req = mock_send.call_args.args[0]
        assert req["action"] == "store"
        assert req["chunk_id"] == "c1"
        assert req["doc_id"] == "d1"
        assert req["text"] == "text"
        assert req["metadata"] == {"key": "val"}

    def test_correct_payload_format(self):
        client = CppClient()
        with patch.object(client, "_send_request", return_value={"status": "ok"}) as mock_send:
            client.store_chunk("c1", "d1", "hello")
        req = mock_send.call_args.args[0]
        assert req["metadata"] == {}  # Default empty dict


# =============================================================================
# search
# =============================================================================

class TestSearch:
    def test_success(self):
        client = CppClient()
        response = {
            "status": "ok",
            "results": [{"chunk_id": "c1", "score": 0.9, "text": "hello"}],
        }
        with patch.object(client, "_send_request", return_value=response):
            results = client.search("query")
        assert len(results) == 1
        assert results[0]["score"] == 0.9

    def test_with_doc_id(self):
        client = CppClient()
        with patch.object(client, "_send_request", return_value={"results": []}) as mock_send:
            client.search("query", doc_id="d1")
        req = mock_send.call_args.args[0]
        assert req["doc_id"] == "d1"

    def test_without_doc_id(self):
        client = CppClient()
        with patch.object(client, "_send_request", return_value={"results": []}) as mock_send:
            client.search("query")
        req = mock_send.call_args.args[0]
        assert "doc_id" not in req


# =============================================================================
# Error paths
# =============================================================================

class TestErrors:
    def test_server_error_response(self):
        client = CppClient()
        response_dict = {"status": "error", "message": "bad request"}
        payload = json.dumps(response_dict).encode("utf-8")
        length_header = struct.pack("!I", len(payload))

        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            mock_sock.recv.side_effect = [length_header, payload]

            with pytest.raises(RuntimeError, match="Server error: bad request"):
                client._send_request({"action": "test"})

    def test_connection_closed_mid_read(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock_cls.return_value = mock_sock
            mock_sock.recv.return_value = b""  # Connection closed

            client = CppClient()
            with pytest.raises(ConnectionError, match="Connection closed"):
                client._send_request({"action": "test"})


# =============================================================================
# _recv_exact
# =============================================================================

class TestRecvExact:
    def test_partial_reads_reassembly(self):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"ab", b"cd", b"ef"]
        result = CppClient._recv_exact(mock_sock, 6)
        assert result == b"abcdef"

    def test_single_read(self):
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b"hello"
        result = CppClient._recv_exact(mock_sock, 5)
        assert result == b"hello"


# =============================================================================
# Config
# =============================================================================

class TestConfig:
    def test_defaults(self):
        client = CppClient()
        assert client.host == "localhost"
        assert client.port == 50051

    def test_custom_host_port(self):
        client = CppClient(host="192.168.1.1", port=9999)
        assert client.host == "192.168.1.1"
        assert client.port == 9999
