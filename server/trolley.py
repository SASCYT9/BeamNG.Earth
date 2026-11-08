"""Trolleybus overhead wires (the owner, 2026-11-09: Ukraine's towns are strung with them; 13,477 roads mapped
trolley_wire=* in OpenStreetMap): over a mapped road, a pair of contact wires above the right-hand lane of each
direction the line runs (0.6 m apart, 5.8 m up: the usual trolleybus contact height), held by span wires across the
street between poles on both sides (the stock street lamp: most such poles carry a lamp too), every SPAN_M.

The roads come from tools/build_osm_extras.py's shipped files (server/data/osm_extras_<cc>.json.gz: {way id:
"both" | "forward" | "backward"}): Layercake's highways have no trolley_wire column and Overpass is never asked at
runtime. A road is matched by its Overture segment's OpenStreetMap way (src_record "w<id>@<v>"). Stations are taken
by arc length along the road's own line, so every tile and anchor places the same poles; a span is drawn by the tile
its first station is in. Wires are render-only (furniture.wire_mesh), the poles Forest rows. Pure, deterministic.

    place(roads, box, way_of, wires) -> rows      (roads: build_tile's (fid, spec, centreline (k, 3), lon))
"""
import glob
import gzip
import json
import logging
import math
import os
import threading

import numpy as np

log = logging.getLogger("earthd.trolley")

DATA_GLOB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "osm_extras_*.json.gz")
SPAN_M = 32.0               # m between the poles along the street
END_CLEAR_M = 6.0           # m kept clear of a road's ends (its junctions: the wires run on, the poles don't)
CONTACT_Z = 5.8             # m over the road: the contact wires
SPAN_Z = 7.3                # m over the road: a span wire at the poles (sagging to the contact wires' hangers)
HANGER_Z = 6.2              # m: the span wire over a contact pair
PAIR_M = 0.6                # m between the two wires of a pair (+ and -)
LANE_M = 3.5                # the pair over the middle of the right-hand lane: this far in from the carriageway's edge / 2
POLE_OFF_M = 0.8            # m beyond the carriageway's edge
CONTACT_R = 0.009           # the wires' drawn half widths (furniture.wire_mesh)
SPAN_R = 0.007
STEP_M = 4.0                # m between a contact wire's points (it follows the road's curves)
G_POLE = "streetlight"      # trees.lua's stock lamp post (9 m)
POLE_H = 9.0
CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "service",
           "living_street"}

_lock = threading.Lock()
_ways = None


def ways():
    """{OSM way id (int): "both" | "forward" | "backward"} of every shipped trolleybus road (loaded once)."""
    global _ways
    with _lock:
        if _ways is None:
            out = {}
            for path in sorted(glob.glob(DATA_GLOB)):
                try:
                    with gzip.open(path, "rt", encoding="utf-8") as f:
                        out.update({int(k): v for k, v in json.load(f).get("trolley", {}).items()})
                except (OSError, ValueError) as ex:
                    log.warning("trolleybus wires: %s: %s", os.path.basename(path), ex)
            _ways = out
        return _ways


def _arclen(p):
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p[:, :2], axis=0).T))])


def _at(line, s, S):
    """Points (n, 3) and unit directions (n, 2) of line at arc lengths s (S: its arc lengths)."""
    s = np.clip(np.asarray(s, np.float64), 0.0, S[-1])
    k = np.clip(np.searchsorted(S, s, side="right") - 1, 0, len(line) - 2)
    seg = S[k + 1] - S[k]
    t = np.where(seg > 1e-9, (s - S[k]) / np.maximum(seg, 1e-9), 0.0)
    p = line[k] + (line[k + 1] - line[k]) * t[:, None]
    d = line[k + 1, :2] - line[k, :2]
    d = d / np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
    return p, d


def _owns(box, x, y):
    x0, y0, x1, y1 = box
    return x0 <= x < x1 and y0 <= y < y1


def pairs(spec, d):
    """The contact pairs' lateral offsets (m, + to the left of the line's direction) of a road of spec under wires
    d ("both" / "forward" / "backward"): the right-hand lane of each direction its trolleybuses run."""
    half = spec.width / 2.0
    lane = max(0.0, half - LANE_M / 2.0)
    sign = -1.0 if not getattr(spec, "dir", 0) or spec.dir >= 0 else 1.0    # (a one-way drawn against its line)
    if spec.oneway:
        return [sign * lane] if d in ("both", "forward") else [-sign * lane]
    out = []
    if d in ("both", "forward"):
        out.append(-lane)                       # (driving on the right: the forward lane to the line's right)
    if d in ("both", "backward"):
        out.append(lane)
    return out


def place(roads, box, way_of, wires):
    """Forest rows [group, x, y, z, yaw, scale, height, rank] of the poles of box (x0, y0, x1, y1), and their wires
    appended to wires (polylines (k, 3), or (points, half width)). way_of(fid) -> the road's OSM way id or None."""
    table = ways()
    if not table:
        return []
    import furniture
    rows = []
    for fid, spec, pts, _lon in roads:
        if spec is None or spec.cls not in CLASSES:
            continue
        wid = way_of(fid)
        d = table.get(wid) if wid is not None else None
        if d is None:
            continue
        line = np.asarray(pts, np.float64)
        if len(line) < 2 or line.shape[1] < 3:
            continue
        S = _arclen(line)
        if S[-1] < 2 * END_CLEAR_M + SPAN_M / 2:
            continue
        offs = pairs(spec, d)
        half = spec.width / 2.0
        k0 = int(math.ceil(END_CLEAR_M / SPAN_M))
        k1 = int(math.floor((S[-1] - END_CLEAR_M) / SPAN_M))
        st = np.arange(k0, k1 + 1) * SPAN_M
        if len(st) < 2:
            continue
        sp, sd = _at(line, st, S)
        for j in range(len(st)):
            p, u = sp[j], sd[j]
            if not _owns(box, p[0], p[1]):
                continue
            n = np.array([-u[1], u[0]])                     # left of the line
            z = float(p[2])
            ends = []
            for side in (1.0, -1.0):                        # a pole each side, its lamp's arm over the road
                q = p[:2] + n * side * (half + POLE_OFF_M)
                out = n * side
                rows.append([G_POLE, round(float(q[0]), 2), round(float(q[1]), 2), round(z, 2),
                             round(furniture._yaw(-out[0], -out[1]), 1), 1.0, POLE_H, 0.0])
                ends.append(q)
            # the span wire: pole top to pole top, dropping to the hangers over each pair
            hang = sorted(offs, reverse=True)
            span = [np.array([ends[0][0], ends[0][1], z + SPAN_Z])]
            for o in hang:
                h = p[:2] + n * o
                span.append(np.array([h[0], h[1], z + HANGER_Z]))
            span.append(np.array([ends[1][0], ends[1][1], z + SPAN_Z]))
            wires.append((np.array(span), SPAN_R))
            if j + 1 >= len(st):
                continue
            # the contact wires to the next station, following the road
            ss = np.linspace(st[j], st[j + 1], max(2, int(math.ceil(SPAN_M / STEP_M)) + 1))
            cp, cd = _at(line, ss, S)
            cn = np.stack([-cd[:, 1], cd[:, 0]], 1)
            sag = 0.12 * np.sin(np.linspace(0.0, math.pi, len(ss)))       # (a little sag between the hangers)
            for o in offs:
                for w in (-PAIR_M / 2, PAIR_M / 2):
                    xy = cp[:, :2] + cn * (o + w)
                    wires.append((np.column_stack([xy, cp[:, 2] + CONTACT_Z - sag]), CONTACT_R))
    return rows
