import asyncio
import json
import time
import uuid
import threading
from typing import Callable, Optional, Tuple

from src.logger import get_logger

log = get_logger("ws_client")

VALID_COMMANDS = {"start", "pause", "stop"}
NOTIFY_THRESHOLD = 5
HEARTBEAT_SECONDS = 15 * 60
BACKOFF_MAX_SECONDS = 30
# 2 ** 5 already exceeds the cap, so a longer outage gains nothing by raising
# the exponent. Clamping it here keeps a five-figure failure count from building
# a five-figure-bit integer on every single retry just to discard it.
BACKOFF_MAX_EXPONENT = 5

Report = Optional[Tuple[str, str]]


def backoff_delay(failure_count: int) -> int:
    """Seconds to wait before retry number `failure_count`."""
    exponent = min(max(failure_count - 1, 0), BACKOFF_MAX_EXPONENT)
    return min(2 ** exponent, BACKOFF_MAX_SECONDS)


class ReconnectLog:
    """Decides what a connection failure is worth logging.

    A closed Streamer.bot is a normal state, not an error, and it can persist
    for days. Logging every retry produced thousands of ERROR lines that buried
    the warnings that actually matter, such as an unusable output folder.

    What survives is the signal: the first failure of a streak, any change in
    the error itself, a periodic heartbeat so a long outage is still visible,
    and the recovery. Returns a (level, message) pair, or None to stay silent.
    """

    def __init__(
        self,
        heartbeat_seconds: int = HEARTBEAT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._heartbeat_seconds = heartbeat_seconds
        self._clock = clock
        self._error: Optional[str] = None
        self._streak_start: Optional[float] = None
        self._last_report = 0.0

    def failure(self, error: str, attempts: int) -> Report:
        now = self._clock()
        if self._streak_start is None:
            self._streak_start = now

        # A changed error is new information: refused means Streamer.bot is
        # closed, unreachable means something else entirely.
        if error != self._error:
            self._error = error
            self._last_report = now
            return ("warning", f"Streamer.bot not reachable: {error}")

        if now - self._last_report >= self._heartbeat_seconds:
            self._last_report = now
            return ("info", f"still disconnected after {attempts} attempts: {error}")

        return None

    def success(self, attempts: int) -> Report:
        if self._streak_start is None:
            return None

        downtime = int(self._clock() - self._streak_start)
        self._streak_start = None
        self._error = None
        return ("info", f"reconnected after {attempts} attempts, down for {downtime}s")


class StreamerbotClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8059,
        on_command: Optional[Callable[[dict], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self._host = host
        self._port = port
        self._on_command = on_command
        self._on_status_change = on_status_change
        self._failure_count = 0
        self._ws = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._reconnect_log = ReconnectLog()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def uri(self) -> str:
        return f"ws://{self._host}:{self._port}/"

    def record_failure(self) -> None:
        self._failure_count += 1

    def record_success(self) -> None:
        self._failure_count = 0

    def should_notify(self) -> bool:
        return self._failure_count >= NOTIFY_THRESHOLD

    def build_subscribe(self) -> str:
        return json.dumps({
            "request": "Subscribe",
            "id": str(uuid.uuid4()),
            "events": {"General": ["Custom"]},
        })

    def build_do_action(self, action_name: str) -> str:
        return json.dumps({
            "request": "DoAction",
            "id": str(uuid.uuid4()),
            "action": {"name": action_name},
        })

    def parse_command(self, msg: dict) -> Optional[dict]:
        event = msg.get("event", {})
        if event.get("source") != "General" or event.get("type") != "Custom":
            return None

        data = msg.get("data", {})
        args = data.get("args")
        if not args or not data.get("useArgs", False):
            return None

        command = args.get("command")
        if command not in VALID_COMMANDS:
            log.warning(
                f"unknown command: {command}",
                extra={"context": "parse_command", "state": f"args={args}"},
            )
            return None

        try:
            timer_index = int(args["timer"])
        except (KeyError, ValueError):
            log.warning(
                "missing or invalid timer index",
                extra={"context": "parse_command", "state": f"args={args}"},
            )
            return None

        result = {"command": command, "timer": timer_index}

        if "duration" in args:
            try:
                result["duration"] = int(args["duration"])
            except ValueError:
                pass

        return result

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self) -> None:
        import websockets

        while self._running:
            try:
                if self._on_status_change:
                    self._on_status_change("connecting")

                async with websockets.connect(self.uri) as ws:
                    self._ws = ws
                    # Read before the reset, so the recovery line can say how
                    # many attempts it took to get back.
                    attempts = self._failure_count
                    self.record_success()

                    if self._on_status_change:
                        self._on_status_change("connected")

                    log.info(
                        f"connected to {self.uri}",
                        extra={"context": "connect", "state": "connected"},
                    )
                    self._report(
                        self._reconnect_log.success(attempts), "connect", attempts
                    )

                    # Wait for Hello, then subscribe
                    hello = await ws.recv()
                    log.info(
                        "received hello",
                        extra={"context": "handshake", "state": "connected"},
                    )

                    await ws.send(self.build_subscribe())
                    sub_response = await ws.recv()
                    log.info(
                        "subscribed to Custom events",
                        extra={"context": "subscribe", "state": "connected"},
                    )

                    async for message in ws:
                        data = json.loads(message)
                        command = self.parse_command(data)
                        if command and self._on_command:
                            self._on_command(command)

            except Exception as e:
                self._ws = None
                self.record_failure()

                if self._on_status_change:
                    status = "error" if self.should_notify() else "reconnecting"
                    self._on_status_change(status)

                self._report(
                    self._reconnect_log.failure(str(e), self._failure_count),
                    "connect_loop",
                    self._failure_count,
                )

                if not self._running:
                    return

                # Exponential backoff: 1s, 2s, 4s, 8s, max 30s
                await asyncio.sleep(backoff_delay(self._failure_count))

    def _report(self, report: Report, context: str, attempts: int) -> None:
        """Emit what ReconnectLog decided was worth saying, if anything."""
        if not report:
            return
        level, message = report
        getattr(log, level)(
            message,
            extra={"context": context, "state": f"failures={attempts}"},
        )

    async def send_do_action(self, action_name: str) -> None:
        if self._ws:
            try:
                await self._ws.send(self.build_do_action(action_name))
                log.info(
                    f"sent DoAction: {action_name}",
                    extra={"context": "send_do_action", "state": "connected"},
                )
            except Exception as e:
                log.error(
                    f"failed to send DoAction: {e}",
                    extra={"context": "send_do_action", "state": f"action={action_name}"},
                )

    def trigger_action(self, action_name: str) -> None:
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(
                self.send_do_action(action_name), self._loop
            )
