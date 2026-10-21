#!/usr/bin/env python3
import argparse
import socket
import sys
import time

def run_listener(host: str, port: int, timeout: int) -> int:
    deadline = time.monotonic() + timeout
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(5)
        server.settimeout(2)
        print(f"LISTENING host={host} port={port} timeout_seconds={timeout}", flush=True)
        print("Waiting for a direct connection. This does not expose the port through any tunnel.", flush=True)
        while time.monotonic() < deadline:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue
            with conn:
                conn.settimeout(5)
                data = conn.recv(256)
                print(f"ACCEPTED peer={addr[0]}:{addr[1]} bytes={len(data)}", flush=True)
                if data == b"GH-RUNNER-DIRECT-PROBE-v1":
                    conn.sendall(b"GH-RUNNER-DIRECT-ACK-v1")
                    print("PASS: expected probe payload received and acknowledged.", flush=True)
                    return 0
                conn.sendall(b"UNEXPECTED-PAYLOAD")
                print("FAIL: unexpected payload.", flush=True)
                return 3
        print("TIMEOUT: no direct TCP connection reached the listener.", flush=True)
        return 4
    except OSError as exc:
        print(f"LISTENER_ERROR: {exc}", file=sys.stderr, flush=True)
        return 2
    finally:
        server.close()

def run_client(host: str, port: int, timeout: float) -> int:
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"GH-RUNNER-DIRECT-PROBE-v1")
            response = sock.recv(256)
        if response == b"GH-RUNNER-DIRECT-ACK-v1":
            print(f"PASS: direct TCP connection and application-level acknowledgement from {host}:{port}")
            return 0
        print(f"FAIL: unexpected acknowledgement: {response!r}", file=sys.stderr)
        return 3
    except (OSError, TimeoutError) as exc:
        print(f"FAIL: cannot establish direct TCP path to {host}:{port}: {exc}", file=sys.stderr)
        print("This is a network feasibility failure; no VM migration was attempted.", file=sys.stderr)
        return 1

def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal direct TCP feasibility probe for GitHub-hosted runners.")
    sub = parser.add_subparsers(dest="mode", required=True)
    listen = sub.add_parser("listen")
    listen.add_argument("--host", default="0.0.0.0")
    listen.add_argument("--port", type=int, required=True)
    listen.add_argument("--timeout", type=int, default=1100)
    connect = sub.add_parser("connect")
    connect.add_argument("--host", required=True)
    connect.add_argument("--port", type=int, required=True)
    connect.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()
    if not (1024 <= args.port <= 65535):
        parser.error("port must be between 1024 and 65535")
    if args.mode == "listen":
        return run_listener(args.host, args.port, args.timeout)
    return run_client(args.host, args.port, args.timeout)

if __name__ == "__main__":
    raise SystemExit(main())
