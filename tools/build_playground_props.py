"""build_playground_props.py: playground equipment and a street kiosk (mod/.../art/shapes/beamngEarth/bne_play_*.dae,
bne_kiosk.dae; the owner, 2026-11-09: Ukraine's yards have playgrounds, its streets kiosks, and the stock levels have
neither). Simple painted-steel shapes from bars and boxes, Z up, origin on the ground at the middle; their materials
in playground.materials.json (loaded by trees.lua). osmextras.py places them where OpenStreetMap maps them.

    python tools/build_playground_props.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "server"))
import dae  # noqa: E402

OUT = os.path.join(HERE, "..", "mod", "beamng_earth", "levels", "beamng_earth", "art", "shapes", "beamngEarth")
# material -> (base colour, metallic, roughness)
MATERIALS = {
    "bne_play_red": ((0.72, 0.12, 0.10), 0.3, 0.45),
    "bne_play_yellow": ((0.93, 0.74, 0.12), 0.1, 0.5),
    "bne_play_blue": ((0.12, 0.32, 0.70), 0.3, 0.45),
    "bne_play_green": ((0.16, 0.50, 0.22), 0.3, 0.45),
    "bne_play_steel": ((0.55, 0.56, 0.58), 0.8, 0.35),
    "bne_play_wood": ((0.55, 0.38, 0.22), 0.0, 0.8),
    "bne_kiosk_wall": ((0.90, 0.90, 0.88), 0.1, 0.5),
    "bne_kiosk_band": ((0.10, 0.36, 0.62), 0.2, 0.45),
    "bne_kiosk_glass": ((0.10, 0.13, 0.16), 0.6, 0.1),
}
FACES = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
         (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


class Shape:
    """Parts per material: positions and triangles appended to."""

    def __init__(self):
        self.parts = {}

    def _add(self, mat, p, t):
        P, T = self.parts.setdefault(mat, ([], []))
        n = sum(len(x) for x in P)
        P.append(np.asarray(p, np.float64))
        T.append(np.asarray(t, np.int64) + n)

    def box(self, mat, x0, x1, y0, y1, z0, z1):
        p = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
             [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
        self._add(mat, p, FACES)

    def slab(self, mat, quad, t):
        """A thin slab over the quadrilateral quad (4 points), t thick (downwards)."""
        q = [np.asarray(x, np.float64) for x in quad]
        self._add(mat, q + [x - (0.0, 0.0, t) for x in q], FACES[:4] + [f[::-1] for f in FACES[:4]] + FACES[4:])

    def bar(self, mat, a, b, w):
        """A square bar of side w from a to b, its ends capped."""
        a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
        d = b - a
        d /= np.linalg.norm(d)
        up = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(d, up)
        u /= np.linalg.norm(u)
        v = np.cross(d, u)
        h = w / 2
        ring = [u * h + v * h, -u * h + v * h, -u * h - v * h, u * h - v * h]
        p = [a + r for r in ring] + [b + r for r in ring]
        self._add(mat, p, FACES)

    def write(self, name):
        geos, nodes = [], []
        for k, (mat, (P, T)) in enumerate(self.parts.items()):
            pos, tris = np.concatenate(P), np.concatenate(T)
            # both windings: thin parts are seen from either side whatever the bar's orientation
            tris = np.concatenate([tris, tris[:, ::-1]])
            g = f"{name}_{k}"
            nv, nt = len(pos), len(tris)
            uv = np.zeros((nv, 2))
            geos.append(
                f'<geometry id="{g}" name="{g}"><mesh>'
                f'<source id="{g}-pos"><float_array id="{g}-pos-a" count="{nv * 3}">{dae._floats(pos.ravel())}'
                f'</float_array><technique_common><accessor source="#{g}-pos-a" count="{nv}" stride="3">'
                f'<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
                f'</accessor></technique_common></source>'
                f'<source id="{g}-uv"><float_array id="{g}-uv-a" count="{nv * 2}">{dae._floats(uv.ravel())}'
                f'</float_array><technique_common><accessor source="#{g}-uv-a" count="{nv}" stride="2">'
                f'<param name="S" type="float"/><param name="T" type="float"/></accessor></technique_common></source>'
                f'<vertices id="{g}-vtx"><input semantic="POSITION" source="#{g}-pos"/></vertices>'
                f'<triangles material="{g}mat" count="{nt}">'
                f'<input semantic="VERTEX" source="#{g}-vtx" offset="0"/>'
                f'<input semantic="TEXCOORD" source="#{g}-uv" offset="1"/>'
                f'<p>{dae._indices(tris, 2)}</p></triangles></mesh></geometry>')
            nodes.append(
                f'<node id="{g}" name="{g}"><instance_geometry url="#{g}"><bind_material><technique_common>'
                f'<instance_material symbol="{g}mat" target="#{mat}"/></technique_common></bind_material>'
                f'</instance_geometry></node>')
        effects = "".join(
            f'<effect id="{m}-fx"><profile_COMMON><technique sid="common"><lambert><diffuse><color>'
            f'{c[0]} {c[1]} {c[2]} 1</color></diffuse></lambert></technique></profile_COMMON></effect>'
            for m, (c, _me, _ro) in MATERIALS.items() if m in self.parts)
        mats = "".join(f'<material id="{m}" name="{m}"><instance_effect url="#{m}-fx"/></material>'
                       for m in MATERIALS if m in self.parts)
        xml = (f'<?xml version="1.0" encoding="utf-8"?>\n'
               f'<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">\n'
               f'<asset><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>\n'
               f'<library_effects>{effects}</library_effects>\n<library_materials>{mats}</library_materials>\n'
               f'<library_geometries>{"".join(geos)}</library_geometries>\n'
               f'<library_visual_scenes><visual_scene id="scene">{"".join(nodes)}</visual_scene>'
               f'</library_visual_scenes>\n<scene><instance_visual_scene url="#scene"/></scene>\n</COLLADA>\n')
        path = os.path.join(OUT, f"{name}.dae")
        with open(path, "w", newline="\n") as f:
            f.write(xml)
        zs = np.concatenate([np.concatenate(P) for P, _T in self.parts.values()])[:, 2]
        print(f"{path}: {zs.max():.2f} m high")
        return float(zs.max() - min(0.0, zs.min()))


def swing():
    """A double swing: an A-frame each end, the top bar 2.3 m up, two seats on chains."""
    s = Shape()
    for x in (-1.5, 1.5):
        for y in (-0.9, 0.9):
            s.bar("bne_play_red", (x, y, 0.0), (x, 0.0, 2.3), 0.07)
    s.bar("bne_play_red", (-1.55, 0.0, 2.3), (1.55, 0.0, 2.3), 0.09)
    for x in (-0.7, 0.7):
        for dx in (-0.22, 0.22):
            s.bar("bne_play_steel", (x + dx, 0.0, 2.25), (x + dx, 0.0, 0.48), 0.02)
        s.box("bne_play_yellow", x - 0.25, x + 0.25, -0.11, 0.11, 0.44, 0.48)
    return s


def slide():
    """A slide: a 1.4 m platform on four posts, a ladder up one side, the chute down the other."""
    s = Shape()
    for x in (-0.5, 0.5):
        for y in (-0.5, 0.5):
            s.bar("bne_play_green", (x, y, 0.0), (x, y, 1.95), 0.08)
    s.box("bne_play_wood", -0.55, 0.55, -0.55, 0.55, 1.35, 1.42)
    for z in (1.65, 1.95):                                          # the railing
        s.bar("bne_play_green", (-0.5, -0.5, z), (0.5, -0.5, z), 0.04)
        s.bar("bne_play_green", (-0.5, -0.5, z), (-0.5, 0.5, z), 0.04)
        s.bar("bne_play_green", (0.5, -0.5, z), (0.5, 0.5, z), 0.04)
    for y in (-0.25, 0.25):                                         # the ladder (-x side)
        s.bar("bne_play_steel", (-1.3, y, 0.0), (-0.55, y, 1.4), 0.05)
    for k in range(1, 6):
        t = k / 6.0
        x, z = -1.3 + 0.75 * t, 1.4 * t
        s.bar("bne_play_steel", (x, -0.25, z), (x, 0.25, z), 0.04)
    a, b = np.array([0.55, 0.0, 1.38]), np.array([3.0, 0.0, 0.25])    # the chute (+x)
    for y in (-0.27, 0.27):
        s.bar("bne_play_yellow", a + (0.0, y, 0.12), b + (0.0, y, 0.12), 0.05)
    s.slab("bne_play_yellow", [a + (0.0, -0.27, 0.0), b + (0.0, -0.27, 0.0), b + (0.0, 0.27, 0.0),
                               a + (0.0, 0.27, 0.0)], 0.03)
    return s


def climb():
    """A climbing frame: a 2 x 2 x 1.8 m cube of bars, a grid each side."""
    s = Shape()
    xs = np.linspace(-1.0, 1.0, 4)
    zs = np.linspace(0.0, 1.8, 4)
    for x in xs:
        for y in xs:
            s.bar("bne_play_blue", (x, y, 0.0), (x, y, 1.8), 0.05)
    for z in zs[1:]:
        for v in xs:
            s.bar("bne_play_blue", (-1.0, v, z), (1.0, v, z), 0.04)
            s.bar("bne_play_blue", (v, -1.0, z), (v, 1.0, z), 0.04)
    return s


def kiosk():
    """A street kiosk: 3 x 2.2 m, 2.5 m high, a glass front (local +y) with a counter, a coloured band under the roof."""
    s = Shape()
    s.box("bne_kiosk_wall", -1.5, 1.5, -1.1, 1.1, 0.0, 2.2)
    s.box("bne_kiosk_glass", -1.35, 1.35, 1.1, 1.13, 0.95, 2.05)          # the front window
    s.box("bne_kiosk_wall", -1.5, 1.5, 1.1, 1.35, 0.9, 0.98)              # the counter
    s.box("bne_kiosk_band", -1.6, 1.6, -1.2, 1.4, 2.2, 2.55)              # the sign band and roof
    return s


def main():
    heights = {}
    for name, make in (("bne_play_swing", swing), ("bne_play_slide", slide), ("bne_play_climb", climb),
                       ("bne_kiosk", kiosk)):
        heights[name] = make().write(name)
    import json
    mats = {}
    for k, (m, (c, metal, rough)) in enumerate(MATERIALS.items()):
        mats[m] = {"name": m, "mapTo": m, "class": "Material", "version": 1.5,
                   "persistentId": f"5e1d9a40-2b7c-4c11-9f3e-0a8b6c2d{k:04x}",
                   "Stages": [{"baseColorFactor": [*c, 1.0], "metallicFactor": metal, "roughnessFactor": rough},
                              {}, {}, {}], "doubleSided": True}
    path = os.path.join(OUT, "playground.materials.json")
    with open(path, "w", newline="\n") as f:
        json.dump(mats, f, indent=2)
        f.write("\n")
    print(path)
    print({k: round(v, 2) for k, v in heights.items()})


if __name__ == "__main__":
    main()
