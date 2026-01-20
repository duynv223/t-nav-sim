import tempfile
import unittest
from pathlib import Path

from core.models import Point, Route, SimpleMotionProfile
from core.reporting import ReporterProtocol, StepStatus, StepUpdate
from core.use_cases.gen import GenRequest, generate_artifacts


class _FakeIqGenerator:
    def __init__(self) -> None:
        self.route_samples = None
        self.route_out_path = None

    def generate(
        self,
        samples,
        out_path: str,
        start_time: str | None = None,
        on_progress=None,
    ) -> str:
        self.route_samples = list(samples)
        self.route_out_path = out_path
        return out_path


class _FailingIqGenerator:
    def generate(
        self,
        samples,
        out_path: str,
        start_time: str | None = None,
        on_progress=None,
    ) -> str:
        raise RuntimeError("route failed")


class GenerateArtifactsTests(unittest.TestCase):
    def test_generate_artifacts_writes_samples_and_reports_status(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0002, 106.0002)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=30.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.1,
            min_turn_speed_kmh=8.0,
        )
        iq_generator = _FakeIqGenerator()
        updates = []

        class _ListReporter(ReporterProtocol):
            def on_setup_steps(self, steps):
                self.steps = steps

            def on_update(self, update: StepUpdate) -> None:
                updates.append(update)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            request = GenRequest(
                route=route,
                profile=profile,
                dt_s=0.1,
                iq_route_path=str(tmp / "route.iq"),
                samples_path=str(tmp / "samples.csv"),
            )

            reporter = _ListReporter()
            result = generate_artifacts(request, iq_generator=iq_generator, reporter=reporter)

            self.assertTrue(result.samples)
            self.assertEqual(result.iq_route_path, request.iq_route_path)
            self.assertEqual(result.samples_path, request.samples_path)

            self.assertTrue(iq_generator.route_samples)
            self.assertEqual(iq_generator.route_out_path, request.iq_route_path)

            samples_path = Path(request.samples_path)
            self.assertTrue(samples_path.exists())
            header = samples_path.read_text(encoding="ascii").splitlines()[0]
            self.assertEqual(header, "t_s,lat,lon,alt_m,speed_mps,bearing_deg")

        step_ids = [update.step_id for update in updates]
        step_statuses = {update.step_id: update.status for update in updates}
        self.assertEqual(
            step_ids,
            ["gen-motion", "gen-motion", "gen-gps-iq", "gen-gps-iq"],
        )
        self.assertEqual(step_statuses["gen-motion"], StepStatus.SUCCESS)
        self.assertEqual(step_statuses["gen-gps-iq"], StepStatus.SUCCESS)

    def test_generate_artifacts_requires_two_points(self) -> None:
        route = Route(points=[Point(10.0, 106.0)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=30.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.1,
            min_turn_speed_kmh=8.0,
        )

        with self.assertRaises(ValueError):
            generate_artifacts(
                GenRequest(route=route, profile=profile),
                iq_generator=_FakeIqGenerator(),
            )

    def test_samples_csv_row_count_matches_samples(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0002, 106.0002)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=30.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.1,
            min_turn_speed_kmh=8.0,
        )
        iq_generator = _FakeIqGenerator()

        with tempfile.TemporaryDirectory() as tmpdir:
            request = GenRequest(
                route=route,
                profile=profile,
                dt_s=0.1,
                iq_route_path=str(Path(tmpdir) / "route.iq"),
                samples_path=str(Path(tmpdir) / "samples.csv"),
            )

            result = generate_artifacts(request, iq_generator=iq_generator)
            lines = Path(request.samples_path).read_text(encoding="ascii").splitlines()
            self.assertEqual(len(lines), len(result.samples) + 1)

    def test_generate_artifacts_reports_failed_step(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0002, 106.0002)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=30.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.1,
            min_turn_speed_kmh=8.0,
        )
        updates = []

        class _ListReporter(ReporterProtocol):
            def on_setup_steps(self, steps):
                self.steps = steps

            def on_update(self, update: StepUpdate) -> None:
                updates.append(update)

        with self.assertRaises(RuntimeError):
            generate_artifacts(
                GenRequest(route=route, profile=profile),
                iq_generator=_FailingIqGenerator(),
                reporter=_ListReporter(),
            )

        self.assertTrue(updates)
        self.assertEqual(updates[-1].step_id, "gen-gps-iq")
        self.assertEqual(updates[-1].status, StepStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
