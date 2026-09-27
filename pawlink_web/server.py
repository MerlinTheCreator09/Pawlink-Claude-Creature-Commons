"""PawLink local dashboard.

Reads the ESP32's USB serial output and streams it to a browser at http://localhost:8000
using Server-Sent Events. Every serial line is shown in the dashboard's log, and:
  - "LCD:<text>"                       -> current LCD contents
  - "Button N (IOx) -> pressed"        -> a press of button N (current firmware)
  - "Button N: <word>"                 -> a press of button N (older firmware)

Usage:
    python server.py                 # auto-detects the ESP32's COM port
    python server.py --port COM8     # or pick it explicitly

Close the Arduino IDE Serial Monitor first - only one program can hold the COM port.
"""

import argparse
import json
import queue
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial
import serial.tools.list_ports

ESPRESSIF_VID = 0x303A  # native USB (ESP32-H2/C3/C6/S3 USB-Serial-JTAG)
USB_UART_VIDS = {0x10C4, 0x1A86}  # CP210x, CH340/CH343 bridges on classic dev boards
IDLE_TEXT = "Press a button"
WORDS = ["cancer", "diabetes", "treats"]
LOG_LIMIT = 200
HISTORY_LIMIT = 50

PRESS_NEW_RE = re.compile(r"^Button (\d)\b.*->\s*pressed", re.IGNORECASE)
PRESS_OLD_RE = re.compile(r"^Button (\d):\s*\S+")

HERE = Path(__file__).parent
INDEX_HTML = HERE / "index.html"


class State:
    """Shared dashboard state plus a fan-out of events to connected browsers."""

    def __init__(self):
        self.lock = threading.Lock()
        self.connected = False
        self.port = None
        self.lcd = IDLE_TEXT
        self.counts = {w: 0 for w in WORDS}
        self.history = []  # [{"word", "ts"}], newest last
        self.log = []  # [{"line", "ts"}], newest last
        self.clients = []  # one queue per open browser tab

    def snapshot(self):
        with self.lock:
            return {
                "type": "snapshot",
                "connected": self.connected,
                "port": self.port,
                "lcd": self.lcd,
                "counts": dict(self.counts),
                "history": list(self.history),
                "log": list(self.log),
            }

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.clients.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def _broadcast(self, event):
        for q in self.clients:
            q.put(event)

    def set_status(self, connected, port):
        with self.lock:
            if (self.connected, self.port) == (connected, port):
                return
            self.connected, self.port = connected, port
            self._broadcast({"type": "status", "connected": connected, "port": port})

    def add_line(self, line):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.log.append({"line": line, "ts": ts})
            del self.log[:-LOG_LIMIT]
            self._broadcast({"type": "log", "line": line, "ts": ts})

            if line.startswith("LCD:"):
                self._set_lcd(line[4:], ts)
                return

            m = PRESS_NEW_RE.match(line) or PRESS_OLD_RE.match(line)
            if not m or not 1 <= int(m.group(1)) <= len(WORDS):
                return
            word = WORDS[int(m.group(1)) - 1]
            self.counts[word] += 1
            self.history.append({"word": word, "ts": ts})
            del self.history[:-HISTORY_LIMIT]
            self._broadcast({"type": "press", "word": word, "ts": ts, "counts": dict(self.counts)})
            # Older firmware never sends LCD: lines, so mirror the press onto the display too
            self._set_lcd(word, ts)

    def _set_lcd(self, text, ts):
        if text == self.lcd:
            return
        self.lcd = text
        self._broadcast({"type": "lcd", "text": text, "ts": ts})


def find_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.vid == ESPRESSIF_VID:
            return p.device
    for p in ports:
        if p.vid in USB_UART_VIDS:
            return p.device
    return None


def serial_worker(state, port_arg, baud):
    """Keeps (re)connecting to the ESP32 and feeds each serial line into state."""
    while True:
        port = port_arg or find_port()
        if not port:
            state.set_status(False, None)
            time.sleep(2)
            continue
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, baud, 1
            # Keep DTR/RTS deasserted so opening the port doesn't reset the board
            ser.dtr = False
            ser.rts = False
            ser.open()
        except serial.SerialException as e:
            print(f"Can't open {port}: {e}")
            state.set_status(False, port)
            time.sleep(2)
            continue

        print(f"Connected to {port} @ {baud}")
        state.set_status(True, port)
        buf = b""
        try:
            while True:
                buf += ser.read(ser.in_waiting or 1)
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        state.add_line(line)
        except (serial.SerialException, OSError) as e:
            print(f"Lost {port}: {e}")
        finally:
            ser.close()
            state.set_status(False, port)
            time.sleep(1)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # keep the console for serial status only

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                body = INDEX_HTML.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/events":
                self.stream_events()
            else:
                self.send_error(404)


        def stream_events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            q = state.subscribe()
            try:
                self.send_event(state.snapshot())
                while True:
                    try:
                        self.send_event(q.get(timeout=15))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")  # keeps the connection alive
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                state.unsubscribe(q)

        def send_event(self, event):
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()

    return Handler


def main():
    parser = argparse.ArgumentParser(description="PawLink local dashboard")
    parser.add_argument("--port", help="Serial port, e.g. COM8 (default: auto-detect)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--http", type=int, default=8000, help="Web server port")
    args = parser.parse_args()

    state = State()
    threading.Thread(target=serial_worker, args=(state, args.port, args.baud), daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.http), make_handler(state))
    server.daemon_threads = True
    print(f"PawLink dashboard: http://localhost:{args.http}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
