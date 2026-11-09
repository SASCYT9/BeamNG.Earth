"""trolley: the overhead wires and their poles over the mapped trolleybus roads."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import roads  # noqa: E402
import trolley  # noqa: E402


class TrolleyTest(unittest.TestCase):
    def setUp(self):
        self.table = trolley.ways()
        self.assertGreater(len(self.table), 13000, "Ukraine's shipped trolleybus roads")
        self.wid = next(w for w, d in self.table.items() if d == "both")
        self.line = np.array([[0.0, 0.0, 10.0], [200.0, 0.0, 12.0]])

    def place(self, spec, way=None, box=(-50.0, -50.0, 300.0, 50.0)):
        wires = []
        rows = trolley.place([("f1", spec, self.line, None)], box, lambda fid: way, wires)
        return rows, wires

    def test_a_two_way_street(self):
        spec = roads.Spec(12.0, "paved", True, "primary", False)
        rows, wires = self.place(spec, self.wid)
        poles = [r for r in rows if r[0] == trolley.G_POLE]
        self.assertGreater(len(poles), 8, "poles both sides every 32 m")
        self.assertTrue(all(abs(abs(r[2]) - (6.0 + trolley.POLE_OFF_M)) < 0.01 for r in poles), "beside the carriageway")
        contact = [w for w, r in wires if r == trolley.CONTACT_R]
        self.assertEqual(len(contact) % 4, 0, "two pairs: one over each direction's right lane")
        ys = sorted({round(float(w[0, 1]), 2) for w in contact})
        self.assertEqual(ys, [-4.55, -3.95, 3.95, 4.55])
        z = np.concatenate([w[:, 2] - np.interp(w[:, 0], self.line[:, 0], self.line[:, 2]) for w in contact])
        self.assertTrue(((z > trolley.CONTACT_Z - 0.2) & (z <= trolley.CONTACT_Z + 1e-6)).all(), "5.8 m up, a little sag")
        spans = [w for w, r in wires if r == trolley.SPAN_R]
        self.assertEqual(len(spans), len(poles) // 2, "a span wire across at every pair of poles")

    def test_kept_clear_under_a_deck(self):
        """furniture.under_decks takes the (points, half width) wires: those under a low deck go."""
        import furniture
        spec = roads.Spec(12.0, "paved", True, "primary", False)
        rows, wires = self.place(spec, self.wid)
        n = len(wires)
        deck = (np.array([[100.0, -40.0, 15.0], [100.0, 40.0, 15.0]]), 6.0)     # 3-5 m over the wires at x = 100
        kept = furniture.under_decks(rows, [deck], wires)
        self.assertLess(len(wires), n, "the wires under the deck removed")
        self.assertTrue(all(isinstance(w, tuple) and len(w) == 2 for w in wires), "the rest keep their widths")
        self.assertLessEqual(len(kept), len(rows))

    def test_one_direction_and_unmapped(self):
        spec = roads.Spec(12.0, "paved", True, "primary", False)
        self.assertEqual(trolley.pairs(spec, "forward"), [-4.25])
        self.assertEqual(trolley.pairs(spec._replace(oneway=True, dir=-1, width=7.0), "both"), [1.75])
        rows, wires = self.place(spec, None)
        self.assertEqual((rows, wires), ([], []), "a road without trolley_wire: nothing")
        rows, wires = self.place(spec._replace(cls="footway"), self.wid)
        self.assertEqual(rows, [])

    def test_only_its_own_spans(self):
        spec = roads.Spec(12.0, "paved", True, "primary", False)
        a = self.place(spec, self.wid, box=(-50.0, -50.0, 100.0, 50.0))
        b = self.place(spec, self.wid, box=(100.0, -50.0, 300.0, 50.0))
        whole = self.place(spec, self.wid)
        self.assertEqual(len(a[0]) + len(b[0]), len(whole[0]), "each pole in one tile")
        self.assertEqual(len(a[1]) + len(b[1]), len(whole[1]))


if __name__ == "__main__":
    unittest.main()
