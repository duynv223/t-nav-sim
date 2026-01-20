import math
import unittest

from core.geo import bearing_deg
from core.models import Point, Route, SimpleMotionProfile
from core.motion import generate_motion_samples


class MotionSampleTests(unittest.TestCase):
    def test_generates_samples_and_monotonic_time(self) -> None:
        route = Route(
            points=[
                Point(10.0, 106.0),
                Point(10.0003, 106.0003),
                Point(10.0006, 106.0000),
            ]
        )
        profile = SimpleMotionProfile(
            cruise_speed_kmh=30.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.2,
            min_turn_speed_kmh=8.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertTrue(samples)
        self.assertAlmostEqual(samples[0].lat, route.points[0].lat)
        self.assertAlmostEqual(samples[0].lon, route.points[0].lon)

        times = [s.t_s for s in samples]
        self.assertTrue(all(t2 > t1 for t1, t2 in zip(times, times[1:])))

    def test_turn_speed_limit_applies(self) -> None:
        route = Route(
            points=[
                Point(10.0, 106.0),
                Point(10.0010, 106.0),
                Point(10.0010, 106.0010),
            ]
        )
        profile = SimpleMotionProfile(
            cruise_speed_kmh=36.0,
            accel_mps2=2.0,
            decel_mps2=2.0,
            turn_slowdown_factor_per_deg=0.3,
            min_turn_speed_kmh=10.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertTrue(samples)

        bearing_first = bearing_deg(
            route.points[0].lat,
            route.points[0].lon,
            route.points[1].lat,
            route.points[1].lon,
        )
        bearing_second = bearing_deg(
            route.points[1].lat,
            route.points[1].lon,
            route.points[2].lat,
            route.points[2].lon,
        )
        turn_angle = abs((bearing_second - bearing_first + 180.0) % 360.0 - 180.0)
        target_kmh = max(
            profile.min_turn_speed_kmh,
            profile.cruise_speed_kmh - profile.turn_slowdown_factor_per_deg * turn_angle,
        )
        target_mps = target_kmh / 3.6

        second_seg_samples = [s for s in samples if math.isclose(s.bearing_deg, bearing_second, abs_tol=1.0)]
        self.assertTrue(second_seg_samples)
        self.assertTrue(all(s.speed_mps <= target_mps + 1e-6 for s in second_seg_samples))

    def test_turn_in_place_adds_rotation_time(self) -> None:
        route = Route(
            points=[
                Point(10.0, 106.0),
                Point(10.0, 106.0010),
                Point(10.0010, 106.0010),
            ]
        )
        profile = SimpleMotionProfile(
            cruise_speed_kmh=18.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.0,
            min_turn_speed_kmh=5.0,
            turn_rate_deg_s=20.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertTrue(samples)

        bearing_first = bearing_deg(
            route.points[0].lat,
            route.points[0].lon,
            route.points[1].lat,
            route.points[1].lon,
        )
        bearing_second = bearing_deg(
            route.points[1].lat,
            route.points[1].lon,
            route.points[2].lat,
            route.points[2].lon,
        )
        turn_angle = abs((bearing_second - bearing_first + 180.0) % 360.0 - 180.0)
        expected_rotation_s = turn_angle / profile.turn_rate_deg_s

        turn_point = route.points[1]
        turn_samples = [
            s
            for s in samples
            if math.isclose(s.lat, turn_point.lat, abs_tol=1e-7)
            and math.isclose(s.lon, turn_point.lon, abs_tol=1e-7)
        ]
        self.assertGreater(len(turn_samples), 1)
        self.assertAlmostEqual(turn_samples[-1].t_s - turn_samples[0].t_s, expected_rotation_s, places=6)
        min_turn_speed = min(s.speed_mps for s in turn_samples)
        self.assertTrue(math.isclose(min_turn_speed, 1.0 / 3.6, abs_tol=1e-6))
        self.assertAlmostEqual(turn_samples[-1].bearing_deg, bearing_second, places=3)

    def test_start_speed_phase_runs_at_fixed_speed(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0010, 106.0)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=18.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.0,
            min_turn_speed_kmh=5.0,
            start_speed_kmh=3.6,
            start_speed_s=3.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertTrue(samples)

        phase_samples = samples[1:4]
        self.assertEqual([s.t_s for s in phase_samples], [1.0, 2.0, 3.0])
        self.assertTrue(all(math.isclose(s.speed_mps, 1.0, abs_tol=1e-6) for s in phase_samples))

    def test_invalid_dt_raises(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0005, 106.0005)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=20.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.0,
            min_turn_speed_kmh=5.0,
        )

        with self.assertRaises(ValueError):
            generate_motion_samples(route, profile, dt_s=0.0)
        with self.assertRaises(ValueError):
            generate_motion_samples(route, profile, dt_s=-1.0)

    def test_single_point_route_returns_empty(self) -> None:
        route = Route(points=[Point(10.0, 106.0)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=25.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.0,
            min_turn_speed_kmh=5.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertEqual(samples, [])

    def test_final_sample_matches_route_end(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0, 106.0010)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=18.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.0,
            min_turn_speed_kmh=5.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=0.5)
        self.assertTrue(samples)
        last = samples[-1]
        self.assertAlmostEqual(last.lat, route.points[-1].lat, places=7)
        self.assertAlmostEqual(last.lon, route.points[-1].lon, places=7)

    def test_speed_never_exceeds_cruise(self) -> None:
        route = Route(
            points=[
                Point(10.0, 106.0),
                Point(10.0004, 106.0004),
                Point(10.0008, 106.0001),
            ]
        )
        profile = SimpleMotionProfile(
            cruise_speed_kmh=22.0,
            accel_mps2=2.0,
            decel_mps2=2.0,
            turn_slowdown_factor_per_deg=0.1,
            min_turn_speed_kmh=6.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertTrue(samples)
        cruise_mps = profile.cruise_speed_kmh / 3.6
        self.assertTrue(all(s.speed_mps <= cruise_mps + 1e-6 for s in samples))

    def test_start_hold_inserts_stationary_samples(self) -> None:
        route = Route(points=[Point(10.0, 106.0), Point(10.0010, 106.0)])
        profile = SimpleMotionProfile(
            cruise_speed_kmh=18.0,
            accel_mps2=1.0,
            decel_mps2=1.0,
            turn_slowdown_factor_per_deg=0.0,
            min_turn_speed_kmh=5.0,
            start_hold_s=2.0,
        )

        samples = generate_motion_samples(route, profile, dt_s=1.0)
        self.assertTrue(samples)
        hold_samples = samples[:3]
        self.assertEqual([s.t_s for s in hold_samples], [0.0, 1.0, 2.0])
        self.assertTrue(all(s.speed_mps == 0.0 for s in hold_samples))
        self.assertTrue(all(s.lat == route.points[0].lat for s in hold_samples))
        self.assertTrue(all(s.lon == route.points[0].lon for s in hold_samples))


if __name__ == "__main__":
    unittest.main()
