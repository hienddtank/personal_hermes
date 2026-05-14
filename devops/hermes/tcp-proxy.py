#!/usr/bin/env python3
import select
import socket
import sys
import threading


def pipe(left, right):
    sockets = [left, right]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [])
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                target = right if source is left else left
                target.sendall(data)
    finally:
        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass


def handle(client, target_host, target_port):
    try:
        upstream = socket.create_connection((target_host, target_port), timeout=10)
    except OSError:
        client.close()
        return
    pipe(client, upstream)


def main():
    if len(sys.argv) != 5:
        print("usage: tcp-proxy.py <listen-host> <listen-port> <target-host> <target-port>", file=sys.stderr)
        return 2

    listen_host, listen_port, target_host, target_port = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((listen_host, listen_port))
    server.listen(128)
    print(f"proxy {listen_host}:{listen_port} -> {target_host}:{target_port}", flush=True)

    while True:
        client, _ = server.accept()
        thread = threading.Thread(target=handle, args=(client, target_host, target_port), daemon=True)
        thread.start()


if __name__ == "__main__":
    raise SystemExit(main())
