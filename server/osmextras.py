"""Playgrounds, waste bins and street kiosks from the shipped OpenStreetMap extracts (the owner, 2026-11-09: Ukraine's
yards and streets; tools/build_osm_extras.py: server/data/osm_extras_<cc>.json.gz "playgrounds", "bins", "kiosks").

A playground gets a swing, a slide and (on a bigger one) a climbing frame round its middle, turned by a hash of its
position, with a bench; a waste bin the stock round bin on its node; a kiosk (tools/build_playground_props.py) on
its node, its window towards the nearest road. worldprops' rows; deterministic: every tile places the same items and
keeps those in its own box.

    rows(frame, box, roads_xy) -> [{"group", "x", "y", "lat", "lon", "lift", "h", "yaw", "rank"}]
"""
import glob
import gzip
import hashlib
import json
import logging
import math
import os
import threading

import numpy as np

log = logging.getLogger("earthd.osmextras")

DATA_GLOB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "osm_extras_*.json.gz")
# trees.lua's groups and the shapes' heights (tools/build_playground_props.py; the stock bin and bench)
SWING, SLIDE, CLIMB, KIOSK, BIN, BENCH = "playswing", "playslide", "playclimb", "kiosk", "bin", "bench"
HEIGHTS = {SWING: 2.36, SLIDE: 1.98, CLIMB: 1.82, KIOSK: 2.55, BIN: 1.1, BENCH: 0.9}
BIG_PLAYGROUND_M = 9.0      # a playground this wide (its radius) gets the climbing frame too
SMALL_PLAYGROUND_M = 3.0    # ... smaller (or a node): the layout as for this radius
KIOSK_ROAD_M = 40.0         # a kiosk faces the nearest road within this far (else a hashed way)

_lock = threading.Lock()
_data = None


def data():
    """{"playgrounds": (n, 3) lat lon r, "bins": (n, 2), "kiosks": (n, 2)} of every shipped file (loaded once)."""
    global _data
    with _lock:
        if _data is None:
            got = {"playgrounds": [], "bins": [], "kiosks": []}
            for path in sorted(glob.glob(DATA_GLOB)):
                try:
                    with gzip.open(path, "rt", encoding="utf-8") as f:
                        d = json.load(f)
                    for k in got:
                        got[k].extend(d.get(k, ()))
                except (OSError, ValueError) as ex:
                    log.warning("osm extras: %s: %s", os.path.basename(path), ex)
            _data = {"playgrounds": np.array(got["playgrounds"], np.float64).reshape(-1, 3),
                     "bins": np.array(got["bins"], np.float64).reshape(-1, 2),
                     "kiosks": np.array(got["kiosks"], np.float64).reshape(-1, 2)}
        return _data


def _h01(*vals):
    h = hashlib.blake2b(repr(vals).encode(), digest_size=8).digest()
    return int.from_bytes(h, "little") / 2.0 ** 64


def _near(frame, box, ll, margin_m=0.0):
    """(indices, x, y) of the rows of ll (n, >=2 lat lon) within box (+ margin) in the frame."""
    if not len(ll):
        return [], np.zeros(0), np.zeros(0)
    x0, y0, x1, y1 = box
    cla, clo, _ = frame.enu_to_geodetic(np.array([x0, x1, x0, x1], np.float64), np.array([y0, y0, y1, y1], np.float64),
                                        np.zeros(4))
    m = 0.001 + margin_m / 80000.0
    k = np.flatnonzero((ll[:, 0] >= cla.min() - m) & (ll[:, 0] <= cla.max() + m) & (ll[:, 1] >= clo.min() - m)
                       & (ll[:, 1] <= clo.max() + m))
    if not len(k):
        return [], np.zeros(0), np.zeros(0)
    e, n, _ = frame.geodetic_to_enu(ll[k, 0], ll[k, 1], np.zeros(len(k)))
    return k.tolist(), np.asarray(e, np.float64), np.asarray(n, np.float64)


def _inside(box, x, y):
    x0, y0, x1, y1 = box
    return x0 <= x < x1 and y0 <= y < y1


def _row(frame, group, x, y, yaw, rank=0.0):
    la, lo, _ = frame.enu_to_geodetic(np.array([x]), np.array([y]), np.zeros(1))
    return {"group": group, "x": float(x), "y": float(y), "lat": float(la[0]), "lon": float(lo[0]), "lift": 0.0,
            "h": HEIGHTS[group], "yaw": float(yaw) % 360.0, "rank": rank}


def playground_layout(r):
    """[(group, x, y, yaw)] of a playground of radius r m in its own frame (+x along its hashed turn)."""
    r = max(SMALL_PLAYGROUND_M, float(r))
    s = min(1.0, r / 8.0)                       # (spread with the playground, never past ~8 m out)
    items = [(SWING, -3.0 * s, 1.5 * s, 0.0), (SLIDE, 2.0 * s, -1.5 * s, 90.0)]
    if r >= BIG_PLAYGROUND_M:
        items.append((CLIMB, 2.5 * s, 3.5 * s, 0.0))
    items.append((BENCH, -3.5 * s, -3.5 * s, 45.0))
    return items


def rows(frame, box, roads_xy=None):
    """worldprops rows of the playgrounds, bins and kiosks whose items stand in box (x0, y0, x1, y1). roads_xy: the
    road polylines near it (a function making them; for the kiosks' facing), or None."""
    d = data()
    out = []
    # playgrounds: every one within reach of the box laid out, its items kept by the tile they stand in
    ks, xs, ys = _near(frame, box, d["playgrounds"], margin_m=12.0)
    for k, cx, cy in zip(ks, xs.tolist(), ys.tolist()):
        la, lo, r = d["playgrounds"][k]
        turn = _h01(round(la, 6), round(lo, 6), "turn") * 360.0
        c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
        for group, lx, ly, yaw in playground_layout(r):
            x, y = cx + lx * c - ly * s, cy + lx * s + ly * c
            if _inside(box, x, y):
                out.append(_row(frame, group, x, y, turn + yaw))
    ks, xs, ys = _near(frame, box, d["bins"])
    for k, x, y in zip(ks, xs.tolist(), ys.tolist()):
        if _inside(box, x, y):
            la, lo = d["bins"][k]
            out.append(_row(frame, BIN, x, y, _h01(round(la, 6), round(lo, 6), "bin") * 360.0))
    ks, xs, ys = _near(frame, box, d["kiosks"])
    lines = None
    for k, x, y in zip(ks, xs.tolist(), ys.tolist()):
        if not _inside(box, x, y):
            continue
        la, lo = d["kiosks"][k]
        yaw = _h01(round(la, 6), round(lo, 6), "kiosk") * 360.0
        if roads_xy is not None:
            if lines is None:
                lines = roads_xy() if callable(roads_xy) else roads_xy
            delta = _road_delta(np.array([x, y]), lines, KIOSK_ROAD_M)
            if delta is not None:               # the window (local +y) towards the road: +x turned 90 deg from it
                yaw = math.degrees(math.atan2(delta[1], delta[0])) - 90.0
        out.append(_row(frame, KIOSK, x, y, yaw))
    return out


def _road_delta(pt, lines, max_m):
    """The vector from pt to the nearest point of a road line within max_m, or None."""
    best, delta = max_m * max_m, None
    for poly in lines:
        if len(poly) < 2:
            continue
        a, b = poly[:-1, :2], poly[1:, :2]
        ab = b - a
        L2 = np.maximum(np.sum(ab * ab, axis=1), 1e-9)
        t = np.clip(np.sum((pt - a) * ab, axis=1) / L2, 0.0, 1.0)
        dv = a + t[:, None] * ab - pt
        d2 = np.sum(dv * dv, axis=1)
        j = int(np.argmin(d2))
        if 0.25 < d2[j] < best:
            best, delta = float(d2[j]), dv[j]
    return delta
