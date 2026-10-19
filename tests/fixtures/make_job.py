"""Writes a small TrichoRendr job folder, the same format the SketchUp exporter writes (see
docs/ARCHITECTURE.md), so the Blender side can be tested without SketchUp.

    blender -b --factory-startup --python tests/fixtures/make_job.py -- <job dir>
    (or: python tests/fixtures/make_job.py <job dir>; stdlib only)

The scene has one of everything the materials rules care about: ground, a paved path, a pool of water
("voda"), a glass pane, a wall, a glowing lamp and three face-me trees with a cut-out PNG texture.
Units are inches, like SketchUp.
"""

import json
import os
import struct
import sys
import zlib

M = 39.37  # inches per meter

MATERIALS = [
    {"name": "default", "color": [1, 1, 1], "alpha": 1.0, "texture": None},
    {"name": "Grass", "color": [0.36, 0.55, 0.26], "alpha": 1.0, "texture": None},
    {"name": "Paving", "color": [0.76, 0.73, 0.69], "alpha": 1.0, "texture": None},
    {"name": "Voda bazén", "color": [0.35, 0.62, 0.72], "alpha": 0.5, "texture": None},
    {"name": "Glass", "color": [0.8, 0.9, 0.95], "alpha": 0.3, "texture": None},
    {"name": "Tree", "color": [0.3, 0.5, 0.2], "alpha": 1.0, "texture": "tree.png"},
    {"name": "Lamp glow", "color": [1.0, 0.85, 0.55], "alpha": 1.0, "texture": None},
    {"name": "Wall", "color": [0.9, 0.9, 0.88], "alpha": 1.0, "texture": None},
]
MAT = {m["name"]: i for i, m in enumerate(MATERIALS)}


class Mesh:
    def __init__(self):
        self.pos, self.uv, self.mat = [], [], []

    def quad(self, a, b, c, d, mat, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        """a b c d counter-clockwise seen from the front."""
        for tri in ((0, 1, 2), (0, 2, 3)):
            corners, coords = (a, b, c, d), [uvs[i] for i in tri]
            for i in tri:
                self.pos += corners[i]
            self.uv += [x for uv in coords for x in uv] * 2  # front, then back
            self.mat += [MAT[mat], MAT[mat]]

    def box(self, x0, y0, z0, x1, y1, z1, mat):
        p = lambda i, j, k: ((x0, x1)[i], (y0, y1)[j], (z0, z1)[k])
        faces = [
            ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),  # top
            ((0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)),  # bottom
            ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),  # -y
            ((1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),  # +y
            ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)),  # -x
            ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),  # +x
        ]
        for f in faces:
            self.quad(*(p(*c) for c in f), mat)


def tree_png(path, w=64, h=96):
    """Canopy disc + trunk on a transparent background (RGBA PNG, stdlib only)."""
    rows = []
    for y in range(h):
        row = bytearray([0])  # filter: none
        for x in range(w):
            canopy = (x - w / 2) ** 2 + (y - h * 0.35) ** 2 < (w * 0.45) ** 2
            trunk = abs(x - w / 2) < 3 and y > h * 0.5
            shade = 0.75 + 0.25 * ((x * 7 + y * 13) % 5) / 4  # a little texture, so it reads as leaves
            if canopy:
                row += bytes([int(70 * shade), int(130 * shade), int(55 * shade), 255])
            elif trunk:
                row += bytes([95, 75, 55, 255])
            else:
                row += bytes([0, 0, 0, 0])
        rows.append(bytes(row))
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))
    open(path, "wb").write(png)


def main(job):
    os.makedirs(job, exist_ok=True)
    tree_png(os.path.join(job, "tree.png"))

    site = Mesh()  # everything static, in model coordinates
    site.quad((-10 * M, -10 * M, 0), (10 * M, -10 * M, 0), (10 * M, 10 * M, 0), (-10 * M, 10 * M, 0), "Grass")
    site.quad((-1 * M, -10 * M, 0.4), (0.5 * M, -10 * M, 0.4), (0.5 * M, 6 * M, 0.4), (-1 * M, 6 * M, 0.4), "Paving")
    site.box(1.3 * M, -1.2 * M, 0, 5.2 * M, 3.2 * M, 0.35 * M, "Paving")  # raised basin
    site.box(1.5 * M, -1 * M, 0.35 * M, 5 * M, 3 * M, 0.42 * M, "Voda bazén")
    site.box(-6 * M, 6 * M, 0, 6 * M, 6.25 * M, 2.6 * M, "Wall")
    site.quad((-4 * M, 2 * M, 0), (-1.6 * M, 2 * M, 0), (-1.6 * M, 2 * M, 2 * M), (-4 * M, 2 * M, 2 * M), "Glass")
    site.box(0.8 * M, 4 * M, 0, 0.95 * M, 4.15 * M, 1.1 * M, "Paving")
    site.box(0.72 * M, 3.92 * M, 1.1 * M, 1.03 * M, 4.23 * M, 1.35 * M, "Lamp glow")

    card = Mesh()  # face-me tree: a vertical card in the XZ plane, front facing -Y, origin at the trunk foot
    card.quad((-1.4 * M, 0, 0), (1.4 * M, 0, 0), (1.4 * M, 0, 4.2 * M), (-1.4 * M, 0, 4.2 * M), "Tree")

    meshes, pos, uv, mat = [], [], [], []
    for mesh in (site, card):
        meshes.append({"first": len(mat) // 2, "count": len(mesh.mat) // 2})
        pos += mesh.pos
        uv += mesh.uv
        mat += mesh.mat

    translate = lambda x, y, z: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]  # column-major, like SketchUp
    trees = [translate(-6 * M, 0, 0), translate(-3 * M, 4.5 * M, 0), translate(7 * M, 5 * M, 0)]
    inst = struct.pack("<Lll", 0, -1, -1) + struct.pack("<16d", *translate(0, 0, 0))
    for i, t in enumerate(trees):
        inst += struct.pack("<Lll", 1, -1, i) + struct.pack("<16d", *t)

    open(os.path.join(job, "pos.bin"), "wb").write(struct.pack(f"<{len(pos)}d", *pos))
    open(os.path.join(job, "uv.bin"), "wb").write(struct.pack(f"<{len(uv)}f", *uv))
    open(os.path.join(job, "mat.bin"), "wb").write(struct.pack(f"<{len(mat)}l", *mat))
    open(os.path.join(job, "inst.bin"), "wb").write(inst)
    scene = {
        "width": 640, "height": 360, "vfov": 40.0, "samples": 8, "ortho": None,
        "eye": [-2 * M, -11 * M, 2.2 * M], "target": [0.5 * M, 2 * M, 0.8 * M], "up": [0, 0, 1],
        "sun": [0.45, -0.35, 0.82], "look": {},
        "materials": MATERIALS, "meshes": meshes, "faceme": trees,
        "triangles": len(mat) // 2, "instances": 1 + len(trees),
    }
    json.dump(scene, open(os.path.join(job, "scene.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"fixture job: {job} ({scene['triangles']} triangles, {scene['instances']} instances)")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(args[0] if args else os.path.join("target", "smoke"))
