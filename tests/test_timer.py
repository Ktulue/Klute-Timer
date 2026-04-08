import time
import threading
from src.timer import Timer


class TestTimerState:
    def test_initial_state_is_idle(self):
        t = Timer(timer_id=0, duration=120)
        assert t.state == "idle"
        assert t.remaining == 120

    def test_start_sets_running(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        assert t.state == "running"
        t.stop()

    def test_pause_from_running(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.pause()
        assert t.state == "paused"
        t.stop()

    def test_resume_from_paused(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.pause()
        t.resume()
        assert t.state == "running"
        t.stop()

    def test_stop_resets_to_idle(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.stop()
        assert t.state == "idle"
        assert t.remaining == 120

    def test_reset_method_does_not_exist(self):
        """Defensive guard: Timer.reset() was deleted as part of the timer
        polish work because there was no UI affordance for it. Stop already
        does halt+reset+clear in one verb. If reset() comes back, it should
        come back via a deliberate spec, not by accident."""
        t = Timer(timer_id=0, duration=120)
        assert not hasattr(t, "reset")

    def test_pause_toggle(self):
        t = Timer(timer_id=0, duration=120)
        t.start()
        t.toggle_pause()
        assert t.state == "paused"
        t.toggle_pause()
        assert t.state == "running"
        t.stop()


class TestTimerCountdown:
    def test_countdown_decrements(self):
        ticks = []
        t = Timer(timer_id=0, duration=3, on_tick=lambda tid, rem: ticks.append(rem))
        t.start()
        time.sleep(2.5)
        t.stop()
        assert len(ticks) >= 2
        assert ticks[0] == 2
        assert ticks[1] == 1

    def test_countdown_reaches_finishing_then_finished(self):
        finished_callback_fired = threading.Event()
        blank_callback_fired = threading.Event()
        t = Timer(
            timer_id=0,
            duration=2,
            hold_seconds=0.1,
            on_finish=lambda tid: finished_callback_fired.set(),
            on_blank=lambda tid: blank_callback_fired.set(),
        )
        t.start()
        finished_callback_fired.wait(timeout=5)
        # When on_finish fires, state should be 'finishing' (the hold has begun)
        assert t.state == "finishing"
        assert t.remaining == 0
        # Wait for the hold to elapse and on_blank to fire
        blank_callback_fired.wait(timeout=2)
        assert t.state == "finished"

    def test_pause_stops_counting(self):
        ticks = []
        t = Timer(timer_id=0, duration=10, on_tick=lambda tid, rem: ticks.append(rem))
        t.start()
        time.sleep(1.5)
        t.pause()
        count_at_pause = len(ticks)
        time.sleep(2)
        assert len(ticks) == count_at_pause
        t.stop()


class TestTimerTriggerPoint:
    def test_trigger_fires_at_threshold(self):
        triggered = threading.Event()

        def on_trigger(tid, action):
            triggered.set()

        t = Timer(
            timer_id=0,
            duration=3,
            trigger_seconds=1,
            trigger_action="TestAction",
            on_trigger=on_trigger,
        )
        t.start()
        triggered.wait(timeout=5)
        assert triggered.is_set()
        t.stop()

    def test_trigger_does_not_fire_without_config(self):
        triggered = threading.Event()
        t = Timer(
            timer_id=0,
            duration=2,
            on_trigger=lambda tid, action: triggered.set(),
        )
        t.start()
        time.sleep(3)
        assert not triggered.is_set()


class TestTimerFormat:
    def test_format_under_one_hour(self):
        t = Timer(timer_id=0, duration=125)
        assert t.format_remaining() == "02:05"

    def test_format_one_hour_plus(self):
        t = Timer(timer_id=0, duration=3661)
        assert t.format_remaining() == "01:01:01"

    def test_format_at_zero(self):
        t = Timer(timer_id=0, duration=60)
        t._remaining = 0
        assert t.format_remaining() == "00:00"

    def test_format_stays_hms_when_crossing_hour(self):
        t = Timer(timer_id=0, duration=3600)
        t._remaining = 59
        assert t.format_remaining() == "00:00:59"

    def test_format_exact_hour(self):
        t = Timer(timer_id=0, duration=3600)
        assert t.format_remaining() == "01:00:00"


class TestTimerOverrideDuration:
    def test_start_with_override_duration(self):
        t = Timer(timer_id=0, duration=120)
        t.start(override_duration=60)
        assert t.remaining == 60
        t.stop()


class TestTimerFinishingState:
    def test_finishing_state_holds_for_hold_seconds(self):
        finish_event = threading.Event()
        blank_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=0.3,
            on_finish=lambda tid: finish_event.set(),
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        # Immediately after on_finish, state must be 'finishing', not 'finished'
        assert t.state == "finishing"
        # on_blank should NOT have fired yet
        assert not blank_event.is_set()
        # Now wait for the hold to elapse
        blank_event.wait(timeout=2)
        assert t.state == "finished"

    def test_finishing_cancelled_by_stop(self):
        finish_event = threading.Event()
        blank_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=2.0,
            on_finish=lambda tid: finish_event.set(),
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        assert t.state == "finishing"
        t.stop()
        assert t.state == "idle"
        # Give the thread a moment to exit
        time.sleep(0.1)
        # on_blank must NOT have fired — Stop interrupts the hold
        assert not blank_event.is_set()

    def test_finishing_cancelled_by_start(self):
        finish_event = threading.Event()
        blank_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=2.0,
            on_finish=lambda tid: finish_event.set(),
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        assert t.state == "finishing"
        t.start()  # interrupt with a new start
        time.sleep(0.05)
        assert t.state == "running"
        assert t.remaining > 0
        assert not blank_event.is_set()
        t.stop()

    def test_pause_during_finishing_is_noop(self):
        finish_event = threading.Event()
        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=1.0,
            on_finish=lambda tid: finish_event.set(),
        )
        t.start()
        finish_event.wait(timeout=5)
        assert t.state == "finishing"
        t.pause()
        # Pause should NOT change the state during finishing
        assert t.state == "finishing"
        t.stop()

    def test_on_finish_callback_exception_does_not_crash_thread(self):
        blank_event = threading.Event()

        def raising_on_finish(tid):
            raise RuntimeError("simulated callback failure")

        t = Timer(
            timer_id=0,
            duration=1,
            hold_seconds=0.2,
            on_finish=raising_on_finish,
            on_blank=lambda tid: blank_event.set(),
        )
        t.start()
        # Even though on_finish raised, the hold should still proceed and on_blank should fire
        blank_event.wait(timeout=3)
        assert blank_event.is_set()
        assert t.state == "finished"


class TestTimerStartAfterPause:
    def test_start_after_pause_resumes_does_not_restart(self):
        """Regression test for bug found in first build:
        Pressing Start while paused must resume from current remaining,
        not reset to full duration."""
        t = Timer(timer_id=0, duration=10)
        t.start()
        time.sleep(2.5)
        t.pause()
        remaining_at_pause = t.remaining
        # remaining should be ~7 or 8 (started at 10, ran for ~2.5s)
        assert remaining_at_pause < 10
        assert remaining_at_pause >= 6  # tolerate timing variance

        t.start()  # Press Start while paused — should resume, not restart
        assert t.state == "running"
        # remaining should still be close to remaining_at_pause, NOT reset to 10
        assert t.remaining <= remaining_at_pause
        assert t.remaining >= remaining_at_pause - 1  # might tick once during the assertion
        t.stop()


class TestTimerDurationValidation:
    def test_start_with_zero_duration_is_rejected(self, caplog):
        t = Timer(timer_id=0, duration=0)
        t.start()
        assert t.state == "idle"
        assert t.remaining == 0
        assert any("rejected" in r.message.lower() for r in caplog.records)

    def test_start_with_negative_duration_is_rejected(self, caplog):
        t = Timer(timer_id=0, duration=-5)
        t.start()
        assert t.state == "idle"
        assert any("rejected" in r.message.lower() for r in caplog.records)

    def test_start_with_zero_override_duration_is_rejected(self):
        t = Timer(timer_id=0, duration=60)
        t.start(override_duration=0)
        assert t.state == "idle"


class TestTimerCallbackSafety:
    def test_on_tick_exception_does_not_crash_thread(self):
        ticks_after_exception = []

        def raising_then_recording_tick(tid, rem):
            if not ticks_after_exception:
                ticks_after_exception.append(rem)
                raise RuntimeError("first tick fails")
            ticks_after_exception.append(rem)

        t = Timer(timer_id=0, duration=4, on_tick=raising_then_recording_tick)
        t.start()
        time.sleep(2.5)
        # The first tick raised but the thread should still have ticked again
        assert len(ticks_after_exception) >= 2
        t.stop()

    def test_on_trigger_exception_does_not_crash_thread(self):
        ticks = []

        def raising_trigger(tid, action):
            raise RuntimeError("trigger fails")

        t = Timer(
            timer_id=0,
            duration=3,
            trigger_seconds=2,
            trigger_action="x",
            on_trigger=raising_trigger,
            on_tick=lambda tid, rem: ticks.append(rem),
        )
        t.start()
        time.sleep(2.5)
        # Trigger should have fired and raised, but countdown continues
        assert len(ticks) >= 2
        t.stop()
