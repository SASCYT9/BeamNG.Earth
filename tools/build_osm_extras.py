#!/usr/bin/env python3
"""Build server/data/osm_extras_<cc>.json.gz: OpenStreetMap features the world server's runtime sources lack, for a
few countries (the owner, 2026-11-09: Ukraine's speed bumps and trolleybus wires). Overture has neither (its
infrastructure classes have no traffic calming; trolley_wire is not in Layercake's highways columns), and Overpass
is never asked at runtime (netfetch: overpass-api.de denied), so they are extracted here once, by a developer, and
shipped as a small data file like bridges_us.npz.

    python3 tools/build_osm_extras.py UA [MD BY ...]

Contents (ODbL, © OpenStreetMap contributors, credited with the map data):
    bumps:   [[lat, lon, kind], ...]   nodes with traffic_calming=* (bump, hump, table, cushion, chicane, ...)
    trolley: {way id: "both" | "forward" | "backward"}   highways under trolleybus wires (trolley_wire=yes /
             forward / backward, trolley_wire:forward / :backward=yes); the roads match them by Overture's
             src_record "w<id>@<version>"
"""
import datetime
import gzip
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "server", "data")
URL = "https://overpass-api.de/api/interpreter"
UA = "BeamNG.Earth-dev (tools/build_osm_extras.py)"


def query(cc):
    q = (f'[out:json][timeout:900];area["ISO3166-1"="{cc}"][admin_level=2]->.c;'
         '(node["traffic_calming"](area.c););out;'
         '(way["highway"]["trolley_wire"](area.c);way["highway"]["trolley_wire:forward"](area.c);'
         'way["highway"]["trolley_wire:backward"](area.c););out tags;')
    req = urllib.request.Request(URL, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=1000) as r:
        return json.load(r)["elements"]


def direction(t):
    """"both" / "forward" / "backward" / None from a way's trolley_wire tags."""
    v = str(t.get("trolley_wire", "")).lower()
    fw = v in ("yes", "forward") or str(t.get("trolley_wire:forward", "")).lower() == "yes"
    bw = v in ("yes", "backward") or str(t.get("trolley_wire:backward", "")).lower() == "yes"
    return "both" if fw and bw else "forward" if fw else "backward" if bw else None


def build(cc):
    els = query(cc)
    bumps, trolley = [], {}
    for e in els:
        t = e.get("tags", {})
        if e["type"] == "node" and t.get("traffic_calming") and t["traffic_calming"] != "no":
            bumps.append([round(e["lat"], 7), round(e["lon"], 7), t["traffic_calming"]])
        elif e["type"] == "way":
            d = direction(t)
            if d:
                trolley[str(e["id"])] = d
    bumps.sort()
    data = {"country": cc, "built": datetime.date.today().isoformat(), "source": "OpenStreetMap (ODbL) via Overpass",
            "bumps": bumps, "trolley": dict(sorted(trolley.items(), key=lambda kv: int(kv[0])))}
    path = os.path.join(OUT, f"osm_extras_{cc.lower()}.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"{cc}: {len(bumps)} traffic calming nodes, {len(trolley)} trolleybus wire ways -> {path} "
          f"({os.path.getsize(path) / 1024:.0f} KB)")


if __name__ == "__main__":
    for cc in sys.argv[1:] or ["UA"]:
        build(cc.upper())
