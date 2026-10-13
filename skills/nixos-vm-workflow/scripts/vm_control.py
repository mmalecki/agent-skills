#!/usr/bin/env python3
"""Bounded QMP requests and synchronized QGA execution for test-owned VMs."""

import argparse
import base64
import json
import socket
import sys
import time


class Connection:
    def __init__(self, path, deadline):
        self.deadline = deadline
        self.socket = socket.socket(socket.AF_UNIX)
        self.stream = None
        try:
            self.remaining()
            self.socket.connect(path)
            self.stream = self.socket.makefile("rb")
        except Exception:
            self.socket.close()
            raise

    def remaining(self):
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError("Control operation exceeded its deadline")
        self.socket.settimeout(seconds)

    def send(self, payload, prefix=b""):
        self.remaining()
        self.socket.sendall(prefix + json.dumps(payload).encode() + b"\n")

    def line(self):
        self.remaining()
        line = self.stream.readline()
        if not line:
            raise ConnectionError("VM control socket closed")
        return line

    def close(self):
        if self.stream is not None:
            self.stream.close()
        self.socket.close()


def result(reply):
    if "error" in reply:
        raise RuntimeError(json.dumps(reply["error"]))
    if "return" not in reply:
        raise RuntimeError("Missing control response: " + json.dumps(reply))
    return reply["return"]


def qmp(path, execute, arguments, deadline):
    conn = Connection(path, deadline)
    try:
        greeting = json.loads(conn.line())
        if "QMP" not in greeting:
            raise RuntimeError("Socket did not provide a QMP greeting")
        for request_id, command, args in [
            (1, "qmp_capabilities", None), (2, execute, arguments)
        ]:
            request = {"execute": command, "id": request_id}
            if args is not None:
                request["arguments"] = args
            conn.send(request)
            while True:
                reply = json.loads(conn.line())
                if reply.get("id") == request_id:
                    value = result(reply)
                    break
        return value
    finally:
        conn.close()


def qga(path, execute, arguments, deadline):
    conn = Connection(path, deadline)
    try:
        sync_id = time.time_ns() % (2 ** 53)
        conn.send({"execute": "guest-sync-delimited", "arguments": {"id": sync_id}}, b"\xff")
        while True:
            line = conn.line()
            marker = line.find(b"\xff")
            if marker >= 0:
                reply = json.loads(line[marker + 1:])
                if reply.get("return") == sync_id:
                    break
        conn.send({"execute": execute, "arguments": arguments})
        return result(json.loads(conn.line()))
    finally:
        conn.close()


def guest_exec(path, command, shell, deadline):
    pid = qga(path, "guest-exec", {
        "path": shell, "arg": ["-lc", command], "capture-output": True
    }, deadline)["pid"]
    while time.monotonic() < deadline:
        status = qga(path, "guest-exec-status", {"pid": pid}, deadline)
        if status.get("exited"):
            for key, stream in [("out-data", sys.stdout), ("err-data", sys.stderr)]:
                stream.write(base64.b64decode(status.get(key, "")).decode(errors="replace"))
                stream.flush()
            return status.get("exitcode", 128 + status.get("signal", 1))
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"Guest command did not finish; PID {pid}. Timeout does not terminate it.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    monitor = commands.add_parser("qmp")
    monitor.add_argument("--execute", required=True)
    monitor.add_argument("--arguments", type=json.loads)
    guest = commands.add_parser("guest-exec")
    guest.add_argument("--command", required=True)
    guest.add_argument("--shell", default="/run/current-system/sw/bin/bash")
    for child in [monitor, guest]:
        child.add_argument("--socket", required=True)
        child.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    deadline = time.monotonic() + args.timeout
    try:
        if args.mode == "qmp":
            print(json.dumps(qmp(args.socket, args.execute, args.arguments, deadline)))
            return 0
        return guest_exec(args.socket, args.command, args.shell, deadline)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"VM control failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
