import json
from src.ws_client import StreamerbotClient


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
