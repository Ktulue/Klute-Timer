import asyncio
import json
import logging
import sys
import types

from src.ws_client import ReconnectLog, StreamerbotClient, backoff_delay


class TestMessageParsing:
    def test_parse_start_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "start", "timer": "1"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "start", "timer": 1}

    def test_parse_start_with_duration(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "start", "timer": "1", "duration": "120"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "start", "timer": 1, "duration": 120}

    def test_parse_pause_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "pause", "timer": "2"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "pause", "timer": 2}

    def test_parse_stop_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "timeStamp": "2026-04-04T18:00:00Z",
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "stop", "timer": "3"},
            },
        }
        result = client.parse_command(msg)
        assert result == {"command": "stop", "timer": 3}

    def test_ignore_non_custom_event(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "event": {"source": "Twitch", "type": "Follow"},
            "data": {},
        }
        result = client.parse_command(msg)
        assert result is None

    def test_ignore_unknown_command(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "event": {"source": "General", "type": "Custom"},
            "data": {
                "eventName": "klute-timer",
                "useArgs": True,
                "args": {"command": "explode", "timer": "1"},
            },
        }
        result = client.parse_command(msg)
        assert result is None

    def test_ignore_missing_args(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = {
            "event": {"source": "General", "type": "Custom"},
            "data": {"eventName": "klute-timer", "useArgs": False, "args": None},
        }
        result = client.parse_command(msg)
        assert result is None


class TestSubscribeMessage:
    def test_build_subscribe(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = client.build_subscribe()
        parsed = json.loads(msg)
        assert parsed["request"] == "Subscribe"
        assert "General" in parsed["events"]
        assert "Custom" in parsed["events"]["General"]


class TestDoActionMessage:
    def test_build_do_action(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        msg = client.build_do_action("Push The Button Reminder")
        parsed = json.loads(msg)
        assert parsed["request"] == "DoAction"
        assert parsed["action"]["name"] == "Push The Button Reminder"


class TestReconnectLogic:
    def test_failure_count_tracks(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        assert client.failure_count == 0
        client.record_failure()
        client.record_failure()
        assert client.failure_count == 2
        assert not client.should_notify()

    def test_notify_after_threshold(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        for _ in range(5):
            client.record_failure()
        assert client.should_notify()

    def test_reset_on_success(self):
        client = StreamerbotClient(host="127.0.0.1", port=8059)
        for _ in range(3):
            client.record_failure()
        client.record_success()
        assert client.failure_count == 0


class FakeClock:
    """A monotonic clock the test advances by hand."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestReconnectLogFirstFailure:
    def test_first_failure_of_a_streak_is_reported(self):
        rl = ReconnectLog(clock=FakeClock())

        level, message = rl.failure("refused", attempts=1)

        assert level == "warning"
        assert "refused" in message

    def test_a_repeat_of_the_same_error_is_silent(self):
        rl = ReconnectLog(clock=FakeClock())
        rl.failure("refused", attempts=1)

        assert rl.failure("refused", attempts=2) is None

    def test_a_different_error_is_reported_even_mid_streak(self):
        rl = ReconnectLog(clock=FakeClock())
        rl.failure("refused", attempts=1)

        level, message = rl.failure("host unreachable", attempts=2)

        assert level == "warning"
        assert "host unreachable" in message

    def test_connection_failures_never_log_at_error(self):
        clock = FakeClock()
        rl = ReconnectLog(clock=clock)
        levels = []

        for attempt in range(1, 400):
            result = rl.failure("refused", attempts=attempt)
            if result:
                levels.append(result[0])
            clock.advance(30)

        assert "error" not in levels


class TestReconnectLogHeartbeat:
    def test_stays_silent_before_the_heartbeat_interval(self):
        clock = FakeClock()
        rl = ReconnectLog(heartbeat_seconds=900, clock=clock)
        rl.failure("refused", attempts=1)
        clock.advance(899)

        assert rl.failure("refused", attempts=30) is None

    def test_reports_once_the_heartbeat_interval_has_passed(self):
        clock = FakeClock()
        rl = ReconnectLog(heartbeat_seconds=900, clock=clock)
        rl.failure("refused", attempts=1)
        clock.advance(900)

        level, message = rl.failure("refused", attempts=30)

        assert level == "info"
        assert "30" in message

    def test_heartbeat_carries_the_current_error(self):
        clock = FakeClock()
        rl = ReconnectLog(heartbeat_seconds=900, clock=clock)
        rl.failure("refused", attempts=1)
        clock.advance(900)

        _, message = rl.failure("refused", attempts=30)

        assert "refused" in message

    def test_heartbeats_do_not_repeat_until_another_interval_passes(self):
        clock = FakeClock()
        rl = ReconnectLog(heartbeat_seconds=900, clock=clock)
        rl.failure("refused", attempts=1)
        clock.advance(900)
        rl.failure("refused", attempts=30)
        clock.advance(899)

        assert rl.failure("refused", attempts=60) is None

    def test_a_day_of_downtime_stays_under_a_hundred_lines(self):
        clock = FakeClock()
        rl = ReconnectLog(heartbeat_seconds=900, clock=clock)
        logged = 0

        # A closed Streamer.bot retries every 30s at the backoff cap.
        for attempt in range(1, 2881):
            if rl.failure("refused", attempts=attempt):
                logged += 1
            clock.advance(30)

        assert logged < 100


class TestReconnectLogRecovery:
    def test_recovery_after_a_streak_is_reported(self):
        clock = FakeClock()
        rl = ReconnectLog(clock=clock)
        rl.failure("refused", attempts=1)
        clock.advance(120)

        level, message = rl.success(attempts=4)

        assert level == "info"
        assert "4" in message

    def test_recovery_without_a_streak_is_silent(self):
        rl = ReconnectLog(clock=FakeClock())

        assert rl.success(attempts=0) is None

    def test_the_next_streak_reports_its_first_failure_again(self):
        rl = ReconnectLog(clock=FakeClock())
        rl.failure("refused", attempts=1)
        rl.success(attempts=1)

        level, _ = rl.failure("refused", attempts=1)

        assert level == "warning"


class TestBackoffDelay:
    def test_first_retry_waits_one_second(self):
        assert backoff_delay(1) == 1

    def test_backoff_doubles(self):
        assert backoff_delay(2) == 2
        assert backoff_delay(3) == 4
        assert backoff_delay(4) == 8

    def test_backoff_caps_at_thirty_seconds(self):
        assert backoff_delay(6) == 30

    def test_a_long_outage_still_returns_the_cap(self):
        assert backoff_delay(15848) == 30


class TestConnectLoopLogging:
    """Drives the real reconnect loop against a Streamer.bot that is never up."""

    def _run_outage(self, monkeypatch, attempts_before_stop=50):
        client = StreamerbotClient()

        refused = ConnectionRefusedError(
            "[WinError 1225] The remote computer refused the network connection"
        )

        def connect(uri):
            raise refused

        fake_websockets = types.ModuleType("websockets")
        fake_websockets.connect = connect
        monkeypatch.setitem(sys.modules, "websockets", fake_websockets)

        tries = {"n": 0}

        async def fake_sleep(delay):
            tries["n"] += 1
            if tries["n"] >= attempts_before_stop:
                client._running = False

        monkeypatch.setattr("src.ws_client.asyncio.sleep", fake_sleep)

        client._running = True
        asyncio.run(client._connect_loop())
        return client, tries["n"]

    def test_a_sustained_outage_logs_no_errors(self, monkeypatch, caplog):
        with caplog.at_level(logging.DEBUG, logger="klute_timer"):
            self._run_outage(monkeypatch)

        assert [r.getMessage() for r in caplog.records if r.levelname == "ERROR"] == []

    def test_a_sustained_outage_warns_exactly_once(self, monkeypatch, caplog):
        with caplog.at_level(logging.DEBUG, logger="klute_timer"):
            self._run_outage(monkeypatch)

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1

    def test_the_one_warning_names_the_underlying_error(self, monkeypatch, caplog):
        with caplog.at_level(logging.DEBUG, logger="klute_timer"):
            self._run_outage(monkeypatch)

        warning = next(r for r in caplog.records if r.levelname == "WARNING")
        assert "WinError 1225" in warning.getMessage()

    def test_every_retry_still_happens(self, monkeypatch, caplog):
        with caplog.at_level(logging.DEBUG, logger="klute_timer"):
            _, tries = self._run_outage(monkeypatch)

        assert tries == 50

    def test_the_failure_count_still_climbs_for_the_status_indicator(
        self, monkeypatch, caplog
    ):
        with caplog.at_level(logging.DEBUG, logger="klute_timer"):
            client, _ = self._run_outage(monkeypatch)

        assert client.failure_count == 50
        assert client.should_notify() is True
