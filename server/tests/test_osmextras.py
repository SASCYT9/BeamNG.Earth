"""osmextras: playgrounds, waste bins and kiosks from the shipped OpenStreetMap extracts."""
import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import geodesy  # noqa: E402
import osmextras  # noqa: E402

LAT, LON = 50.45, 30.52


class OsmExtrasTest(unittest.TestCase):
    def setUp(self):
        self.saved = osmextras._data
        f = geodesy.EnuFrame(LAT, LON)
        self.f = f

        def ll(x, y):
            la, lo, _ = f.enu_to_geodetic(np.array([x]), np.array([y]), np.zeros(1))
            return float(la[0]), float(lo[0])
        osmextras._data = {"playgrounds": np.array([[*ll(0.0, 0.0), 12.0], [*ll(60.0, 0.0), 0.0]]),
                           "bins": np.array([ll(10.0, 10.0)]), "kiosks": np.array([ll(0.0, 30.0)])}

    def tearDown(self):
        osmextras._data = self.saved

    def test_a_playground_round_its_middle(self):
        rows = osmextras.rows(self.f, (-50.0, -50.0, 50.0, 50.0))
        big = [r for r in rows if math.hypot(r["x"], r["y"]) < 9.0]
        self.assertEqual(sorted(r["group"] for r in big), ["bench", "playclimb", "playslide", "playswing"])
        self.assertTrue(all(abs(r["h"] - osmextras.HEIGHTS[r["group"]]) < 1e-9 for r in big))
        small = [r for r in osmextras.rows(self.f, (50.0, -50.0, 100.0, 50.0)) if r["group"].startswith("play")]
        self.assertEqual(sorted(r["group"] for r in small), ["playslide", "playswing"], "a mapped point: no frame")

    def test_bins_and_a_kiosk_facing_its_road(self):
        road = [np.array([[-100.0, 40.0], [100.0, 40.0]])]          # a road 10 m north of the kiosk
        rows = osmextras.rows(self.f, (-50.0, -50.0, 50.0, 50.0), lambda: road)
        bins = [r for r in rows if r["group"] == "bin"]
        self.assertEqual(len(bins), 1)
        self.assertAlmostEqual(bins[0]["x"], 10.0, delta=0.01)
        kiosk = [r for r in rows if r["group"] == "kiosk"][0]
        a = math.radians(kiosk["yaw"])
        front = (-math.sin(a), math.cos(a))                             # its local +y
        self.assertGreater(front[1], 0.99, "the window towards the road")

    def test_each_item_in_one_tile(self):
        whole = osmextras.rows(self.f, (-100.0, -100.0, 100.0, 100.0))
        parts = [r for box in ((-100.0, -100.0, 0.0, 100.0), (0.0, -100.0, 100.0, 100.0))
                 for r in osmextras.rows(self.f, box)]
        self.assertEqual(len(whole), len(parts))


if __name__ == "__main__":
    unittest.main()
