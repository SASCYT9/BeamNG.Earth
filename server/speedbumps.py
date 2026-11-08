"""Speed bumps (the owner, 2026-11-09: Ukraine's "lying policemen", 5,284 mapped in OpenStreetMap): the mapped
traffic_calming nodes as the stock rubber bump (the Italy / East Coast levels' speedbump_01a: 6 m long across the
road, 0.54 m along it, 12 cm over its base), laid across the road the node is on, solid near the car (trees.lua's
Forest items collide within SOLID_M).

The nodes come from tools/build_osm_extras.py's shipped files (server/data/osm_extras_<cc>.json.gz): Overture has no
traffic calming and Overpass is never asked at runtime. Forest items scale only uniformly, so a narrow road's bump
is the stock one scaled down (its height with it) and a wide road gets several side by side. Pure, deterministic.

    rows(frame, box, lines) -> [{"group", "x", "y", "lat", "lon", "lift", "h", "yaw", "rank"}]   (worldprops' form)
"""
import glob
import gzip
import json
import logging
import math
import os
import threading

import numpy as np

log = logging.getLogger("earthd.speedbumps")

DATA_GLOB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "osm_extras_*.json.gz")
GROUP = "speedbump"
BUMP_LEN_M = 6.0                # the stock bump's length (its local x: across the road)
BUMP_H = 0.166                  # its vertical size (the catalog height, trees.lua): -4.6 .. 12.0 cm
SINK_M = 0.05                   # sunk this far into the road (scaled with it): ~7 cm showing, a real rubber bump's 5-7
# the kinds laid as a bump (traffic_calming=*: OSM's values; chicanes, islands, chokers and rumble strips are not one)
KINDS = {"bump", "hump", "table", "yes", "mini_bumps", "cushion", "speed_bump", "speed_hump"}
# the carriageway a bump spans, by the road's class (m; two-way): a node on another class (a footway) is not one
WIDTH_M = {"residential": 6.0, "living_street": 5.0, "service": 4.0, "unclassified": 6.0, "tertiary": 7.0,
           "secondary": 8.0, "primary": 9.0, "track": 3.5}
SNAP_M = 3.0                    # a node farther than this from a road of those classes is left out
MIN_SCALE = 0.55                # a narrower road's bump no smaller than this (3.3 m long)

_lock = threading.Lock()
_data = None


def points():
    """(lat (n,), lon (n,), kinds [n]) of every shipped bump of KINDS (loaded once)."""
    global _data
    with _lock:
        if _data is None:
            lat, lon, kind = [], [], []
            for path in sorted(glob.glob(DATA_GLOB)):
                try:
                    with gzip.open(path, "rt", encoding="utf-8") as f:
                        for la, lo, k in json.load(f).get("bumps", ()):
                            if k in KINDS:
                                lat.append(float(la))
                                lon.append(float(lo))
                                kind.append(k)
                except (OSError, ValueError) as ex:
                    log.warning("speed bumps: %s: %s", os.path.basename(path), ex)
            _data = (np.array(lat, np.float64), np.array(lon, np.float64), kind)
        return _data


def _nearest(p, lines):
    """(distance, unit direction, class) of the nearest segment of lines [(xy (k, 2), class)] to p, or None."""
    best = None
    for xy, cls in lines:
        if len(xy) < 2 or cls not in WIDTH_M:
            continue
        if (xy[:, 0].min() > p[0] + SNAP_M or xy[:, 0].max() < p[0] - SNAP_M
                or xy[:, 1].min() > p[1] + SNAP_M or xy[:, 1].max() < p[1] - SNAP_M):
            continue
        a, b = xy[:-1], xy[1:]
        ab = b - a
        L2 = np.maximum(np.sum(ab * ab, axis=1), 1e-9)
        t = np.clip(np.sum((p - a) * ab, axis=1) / L2, 0.0, 1.0)
        d = np.hypot(*(a + t[:, None] * ab - p).T)
        k = int(np.argmin(d))
        if d[k] <= SNAP_M and (best is None or d[k] < best[0]):
            best = (float(d[k]), ab[k] / math.sqrt(L2[k]), cls)
    return best


def pieces(width):
    """(count, uniform scale) of stock bumps side by side spanning a carriageway of width m."""
    n = max(1, int(math.ceil(width / BUMP_LEN_M - 0.1)))
    return n, max(MIN_SCALE, min(1.0, width / (n * BUMP_LEN_M)))


def rows(frame, box, lines):
    """worldprops rows of the bumps in box (x0, y0, x1, y1, the frame's metres); lines: [(xy (k, 2), class)] of the
    roads around it in the frame (or a function making them)."""
    lat, lon, kind = points()
    if not len(lat):
        return []
    x0, y0, x1, y1 = box
    # (the box's corners in degrees, with a margin: only the bumps near the tile are put into the frame)
    cla, clo, _ = frame.enu_to_geodetic(np.array([x0, x1, x0, x1], np.float64), np.array([y0, y0, y1, y1], np.float64),
                                        np.zeros(4))
    m = 0.001
    near = np.flatnonzero((lat >= cla.min() - m) & (lat <= cla.max() + m) & (lon >= clo.min() - m)
                          & (lon <= clo.max() + m))
    if not len(near):
        return []
    e, n, _ = frame.geodetic_to_enu(lat[near], lon[near], np.zeros(len(near)))
    lines = lines() if callable(lines) else lines           # (made only when a bump is near: worldprops._Once)
    out = []
    for k, x, y in zip(near.tolist(), np.asarray(e).tolist(), np.asarray(n).tolist()):
        if not (x0 <= x < x1 and y0 <= y < y1):
            continue
        got = _nearest(np.array([x, y]), lines)
        if got is None:
            continue
        _d, u, cls = got
        across = np.array([-u[1], u[0]])            # the bump's local +x: across the road
        yaw = math.degrees(math.atan2(across[1], across[0])) % 360.0
        count, s = pieces(WIDTH_M[cls])
        for j in range(count):
            off = (j - (count - 1) / 2) * BUMP_LEN_M * s
            px, py = x + across[0] * off, y + across[1] * off
            la, lo, _ = frame.enu_to_geodetic(np.array([px]), np.array([py]), np.zeros(1))
            out.append({"group": GROUP, "x": px, "y": py, "lat": float(la[0]), "lon": float(lo[0]),
                        "lift": -SINK_M * s, "h": BUMP_H * s, "yaw": yaw, "rank": 0.0, "kind": kind[k]})
    return out
