import errno
import unittest
from unittest.mock import patch

from dsim.core.models import MotionSample
from dsim.core.reporting import StepStatus
from dsim.core.use_cases.play import PlayRequest, play_simulation


class _FakeGpsTransmitter:
    def __init__(self) -> None:
        self.paths = []

    def play(self, iq_path: str) -> None:
        self.paths.append(iq_path)


class _FakeController:
    def __init__(self) -> None:
        self.speeds = []
        self.bearings = []
        self.stop_calls = 0
        self.prepared = []

    def prepaire_start_deg(self, bearing_deg: float) -> None:
        self.prepared.append(bearing_deg)

    def set_speed_kmh(self, speed_kmh: float) -> None:
        self.speeds.append(speed_kmh)

    def set_bearing_deg(self, bearing_deg: float) -> None:
        self.bearings.append(bearing_deg)

    def stop(self) -> None:
        self.stop_calls += 1


class _UnavailableGpsTransmitter:
    def play(self, iq_path: str) -> None:
        raise OSError(errno.ENODEV, "device missing")


class _FakeReporter:
    def __init__(self) -> None:
        self.steps = []
        self.updates = []

    def on_setup_steps(self, steps) -> None:
        self.steps = steps

    def on_update(self, update) -> None:
        self.updates.append(update)


class PlaySimulationTests(unittest.TestCase):
    def test_play_simulation_orders_gps_and_motion(self) -> None:
        samples = [
            MotionSample(t_s=0.0, lat=0.0, lon=0.0, speed_mps=0.0, bearing_deg=0.0),
            MotionSample(t_s=0.1, lat=0.0, lon=0.0, speed_mps=10.0, bearing_deg=90.0),
        ]
        gps = _FakeGpsTransmitter()
        ctrl = _FakeController()
        motions = []
        reporter = _FakeReporter()

        with patch("time.sleep") as sleep_mock:
            play_simulation(
                PlayRequest(samples=samples, iq_route_path="route.iq"),
                gps_transmitter=gps,
                controller=ctrl,
                reporter=reporter,
                on_motion=motions.append,
            )

        self.assertEqual(gps.paths, ["route.iq"])
        self.assertEqual(ctrl.stop_calls, 2)
        self.assertEqual(ctrl.prepared, [0.0])
        self.assertEqual(ctrl.bearings, [0.0, 90.0])
        self.assertEqual(ctrl.speeds, [0.0, 36.0])
        self.assertEqual(motions, samples)
        self.assertEqual([step.id for step in reporter.steps], ["play"])
        updates_by_step = {}
        for update in reporter.updates:
            updates_by_step.setdefault(update.step_id, []).append(update)
        self.assertEqual(updates_by_step["play"][-1].status, StepStatus.SUCCESS)
        self.assertTrue(
            any(
                update.status is StepStatus.RUNNING and update.local_progress > 0
                for update in updates_by_step["play"]
            )
        )
        self.assertEqual(sleep_mock.call_count, 1)
        sleep_arg = sleep_mock.call_args.args[0]
        self.assertAlmostEqual(sleep_arg, 0.1, places=6)

    def test_play_simulation_requires_samples(self) -> None:
        gps = _FakeGpsTransmitter()
        ctrl = _FakeController()
        with self.assertRaises(ValueError):
            play_simulation(
                PlayRequest(samples=[], iq_route_path="route.iq"),
                gps_transmitter=gps,
                controller=ctrl,
            )

    def test_play_simulation_stops_on_missing_gps_device(self) -> None:
        samples = [
            MotionSample(t_s=0.0, lat=0.0, lon=0.0, speed_mps=0.0, bearing_deg=0.0),
            MotionSample(t_s=0.1, lat=0.0, lon=0.0, speed_mps=10.0, bearing_deg=90.0),
        ]
        gps = _UnavailableGpsTransmitter()
        ctrl = _FakeController()

        class _InlineThread:
            def __init__(self, target, args=(), daemon=None) -> None:
                self._target = target
                self._args = args

            def start(self) -> None:
                self._target(*self._args)

            def join(self) -> None:
                return None

        with patch("dsim.core.use_cases.play.threading.Thread", _InlineThread):
            with self.assertRaises(OSError) as ctx:
                play_simulation(
                    PlayRequest(samples=samples, iq_route_path="route.iq"),
                    gps_transmitter=gps,
                    controller=ctrl,
                )

        self.assertEqual(ctx.exception.errno, errno.ENODEV)
        self.assertEqual(ctrl.stop_calls, 2)


if __name__ == "__main__":
    unittest.main()
