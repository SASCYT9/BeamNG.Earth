"""speedbumps: the shipped OpenStreetMap traffic_calming nodes laid across their road."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import geodesy  # noqa: E402
import speedbumps  # noqa: E402


class SpeedBumpTest(unittest.TestCase):
    def setUp(self):
        lat, lon, kinds = speedbumps.points()
        self.assertGreater(len(lat), 4000, "Ukraine's shipped bumps")
        self.assertTrue(set(kinds) <= speedbumps.KINDS)
        # a bump in Kyiv: the frame centred on it
        k = int(np.argmin(np.hypot(lat - 50.45, lon - 30.52)))
        self.lat, self.lon = float(lat[k]), float(lon[k])
        self.f = geodesy.EnuFrame(self.lat, self.lon)

    def road(self, cls, angle_deg):
        a = math.radians(angle_deg)
        u = np.array([math.cos(a), math.sin(a)])
        return [(np.array([-u * 60.0, u * 60.0]), cls)]

    def test_across_its_road(self):
        rows = [r for r in speedbumps.rows(self.f, (-20.0, -20.0, 20.0, 20.0), self.road("residential", 30.0))
                if math.hypot(r["x"], r["y"]) < 1.0]
        self.assertEqual(len(rows), 1, "one 6 m bump across a residential street")
        r = rows[0]
        self.assertAlmostEqual(r["yaw"], 120.0, delta=0.5, msg="its length (local +x) across the road")
        self.assertAlmostEqual(r["h"], speedbumps.BUMP_H, delta=1e-9)
        self.assertLess(r["lift"], 0.0, "sunk a little into the road")
        self.assertEqual(r["group"], "speedbump")

    def test_narrow_and_wide_roads(self):
        self.assertEqual(speedbumps.pieces(4.0), (1, 4.0 / 6.0))
        n, s = speedbumps.pieces(9.0)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(n * s * speedbumps.BUMP_LEN_M, 9.0)
        lazy = lambda: self.road("primary", 0.0)        # noqa: E731
        rows = [r for r in speedbumps.rows(self.f, (-20.0, -20.0, 20.0, 20.0), lazy) if abs(r["x"]) < 1 and abs(r["y"]) < 5]
        self.assertEqual(len(rows), 2, "two side by side across a 9 m road")
        self.assertAlmostEqual(abs(rows[0]["y"] - rows[1]["y"]), 4.5, delta=0.01)

    def test_not_on_a_footway_or_far_from_a_road(self):
        near = lambda rows: [r for r in rows if math.hypot(r["x"], r["y"]) < 1.0]     # noqa: E731
        self.assertEqual(near(speedbumps.rows(self.f, (-20.0, -20.0, 20.0, 20.0), self.road("footway", 0.0))), [])
        far = [(np.array([[-60.0, 10.0], [60.0, 10.0]]), "residential")]
        self.assertEqual(near(speedbumps.rows(self.f, (-20.0, -20.0, 20.0, 20.0), far)), [])

    def test_only_its_own_box(self):
        rows = speedbumps.rows(self.f, (100.0, 100.0, 300.0, 300.0), self.road("residential", 30.0))
        self.assertFalse(any(math.hypot(r["x"], r["y"]) < 1.0 for r in rows))


if __name__ == "__main__":
    unittest.main()
