"""Short 1 (V04 conical train wheels), A1 realistic look. Script: SCRIPT.md (v4). Shot timing: timing.json (estimated until the voice exists).
Everything is modelled here with the A1 kit (../../kit/a1kit.py): track, wheelsets, bogies, a generic loco + coaches, an x-ray car with its differential.
Places: MAIN curve at the origin (train, S1/S3b/S5/S6/S8) | CAR road at Y=-600 (S2) | STAND at Y=600 (S3a, S4) | HUNT straight at Y=1200 (S7).
Run: blender -b --factory-startup --python build.py   (env: PCT, SPP, FRAMES, OUT)"""
import bpy, bmesh, math, os, sys, json, random
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..", "kit"))
from mathutils import Vector, Matrix
from a1kit import (scene, key, link, mesh_obj, bm_obj, box, plain, pbr, steel, rust, gravel, concrete, grass, asphalt, glow, no_light,  # noqa: E402
                   xray, _noise_mix, photo_sky, camera, aim, fill_light, cycles, render)

random.seed(4)
T = json.load(open(os.path.join(HERE, "timing.json"))); FPS = T["fps"]; SH = {s["id"]: s for s in T["shots"]}
def F(sec): return int(round(sec * FPS)) + 1
def span(sid): s = SH[sid]; return F(s["start"]), F(s["end"]) - 1
N = F(T["shots"][-1]["end"]) - 1
sc = scene(N)
Z_CAR, Z_STAND, Z_HUNT = Vector((0, -600, 0)), Vector((0, 600, 0)), Vector((0, 1200, 0))

# ---------- dimensions (metres; broad-gauge-like, visual only, not stated in the narration) ----------
RAIL_Z = 0.372; HALF_G = 0.874; WHEEL_R = 0.4575; AXLE_Z = RAIL_Z + WHEEL_R; BACK = 0.803   # rail top, rail-centre offset, wheel radius
REAL_TAPER, EXAG_TAPER = 1 / 20, 1 / 3

# ---------- materials ----------
M = {"steel": steel(), "wheel": steel("wheel_steel", (0.5, 0.5, 0.51), 0.38), "tread": steel("tread", (0.75, 0.76, 0.77), 0.14),
     "rail_top": steel("rail_top", (0.8, 0.8, 0.81), 0.12), "rust": rust(), "ballast": gravel(), "sleeper": concrete(), "grass": grass(),
     "asphalt": asphalt(), "paint_white": plain("line_white", (0.8, 0.8, 0.78), 0.6), "dark": plain("dark", (0.03, 0.03, 0.035), 0.5, metal=0.4),
     "spring": plain("spring", (0.08, 0.09, 0.1), 0.35, metal=0.8), "damper": plain("damper", (0.75, 0.55, 0.02), 0.35, coat=0.4),
     "bogie": pbr("bogie", "blue_metal_plate", 0.6, (0.05, 0.05, 0.055), (0.35, 0.6), 0.5, metal=0.3),
     "coach": pbr("coach_red", "blue_metal_plate", 0.25, (0.32, 0.025, 0.02), (0.22, 0.4), 0.35, coat=0.4),
     "coach_grey": pbr("coach_grey", "blue_metal_plate", 0.25, (0.33, 0.34, 0.36), (0.25, 0.45), 0.35, coat=0.3),
     "loco": pbr("loco", "blue_metal_plate", 0.25, (0.62, 0.63, 0.66), (0.22, 0.4), 0.35, coat=0.4),
     "glass": plain("glass", (0.01, 0.012, 0.016), 0.04, coat=1.0), "tick": plain("tick", (0.85, 0.85, 0.8), 0.5),
     "rubber": plain("rubber", (0.02, 0.02, 0.022), 0.75), "rim": steel("rim", (0.7, 0.71, 0.72), 0.25), "xray": xray(),
     "leaf": _noise_mix("leaf", (0.015, 0.05, 0.01), (0.05, 0.12, 0.02), 3.0, 0.9, 0.4), "bark": plain("bark", (0.06, 0.04, 0.025), 0.9),
     "red_glow": glow("red_glow", (1.0, 0.05, 0.02), 6.0, 0.9), "cyan_glow": glow("cyan_glow", (0.1, 0.75, 1.0), 5.0, 0.85),
     "orange_glow": glow("orange_glow", (1.0, 0.45, 0.05), 6.0, 0.9), "green_glow": glow("green_glow", (0.15, 1.0, 0.35), 4.0, 0.8),
     "backdrop": plain("backdrop", (0.06, 0.08, 0.11), 0.8)}

# ---------- MAIN path: straight along +X, then a left curve, then straight ----------
L0, R, ARC = 260.0, 80.0, math.radians(110)
L1 = L0 + R * ARC; LTOT = L1 + 260.0
def path(s):
    """(position, heading) at arc length s (2D, z = 0)."""
    if s <= L0: return Vector((s - L0, 0, 0)), 0.0
    if s <= L1: p = (s - L0) / R; return Vector((R * math.sin(p), R - R * math.cos(p), 0)), p
    p = ARC; e = Vector((R * math.sin(p), R - R * math.cos(p), 0)); d = s - L1
    return e + Vector((math.cos(p), math.sin(p), 0)) * d, p
def frame_at(s, lateral=0.0, up=0.0):
    p, h = path(s); n = Vector((-math.sin(h), math.cos(h), 0))
    return p + n * lateral + Vector((0, 0, up)), h

def sweep(name, s0, s1, ds, profile, lat, mats, idx_fn=None, loc=(0, 0, 0), pathf=None):
    """Sweep a 2D profile (u lateral, v up) along the path from s0 to s1, offset sideways by lat."""
    pathf = pathf or path; ss = [s0 + i * ds for i in range(int((s1 - s0) / ds) + 1)]; k = len(profile); v, f, idx = [], [], []
    for s in ss:
        p, h = pathf(s); n = Vector((-math.sin(h), math.cos(h), 0))
        for u, vv in profile: v.append(p + n * (lat + u) + Vector((0, 0, vv)))
    for i in range(len(ss) - 1):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k; f.append((a, b, b + k, a + k))
            if idx_fn: idx.append(idx_fn(profile[j], profile[(j + 1) % k]))
    return mesh_obj(name, v, f, mats, idx or None, smooth=True, sharp=40, loc=loc, normals=False)

RAIL_P = [(-0.075, 0), (0.075, 0), (0.075, 0.012), (0.012, 0.03), (0.009, 0.115), (0.036, 0.13), (0.036, 0.172), (-0.036, 0.172), (-0.036, 0.13), (-0.009, 0.115), (-0.012, 0.03), (-0.075, 0.012)]
RAIL_P = [(u, v + 0.2) for u, v in RAIL_P]                       # rail foot on the sleeper top (z 0.2), head top at 0.372
def track(prefix, s0, s1, pathf=None, loc=(0, 0, 0), ballast=True):
    top = lambda a, b: 0 if (a[1] > 0.36 and b[1] > 0.36) else 1
    for side in (-1, 1): sweep(f"{prefix}_rail{side}", s0, s1, 0.5, RAIL_P, side * HALF_G, [M["rail_top"], M["rust"]], top, loc, pathf)
    if ballast:
        sweep(f"{prefix}_ballast", s0, s1, 1.0, [(-2.9, -0.4), (2.9, -0.4), (1.75, 0.13), (-1.75, 0.13)], 0, [M["ballast"]], loc=loc, pathf=pathf)
    bm = bmesh.new(); s = s0
    while s < s1:
        p, h = (pathf or path)(s)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(p + Vector((0, 0, 0.095))) @ Matrix.Rotation(h, 4, "Z") @ Matrix.Diagonal((0.26, 2.75, 0.21, 1)))
        s += 0.65
    bm_obj(f"{prefix}_sleepers", bm, [M["sleeper"]], loc=loc)

# ---------- wheelset (lathe), with a shape key that exaggerates the taper ----------
def wheel_profile(taper):
    t0 = 0.035; tr = lambda y: WHEEL_R - (y - t0) * taper
    # hub (r 0.10-0.20) -> thin web -> rim with flange (inner side, y = 0) and tapered tread
    return [(0.10, 0.0), (0.19, 0.0), (0.20, 0.05), (0.37, 0.05), (0.38, 0.0), (0.48, 0.0), (0.487, 0.008), (0.484, 0.018), (0.47, 0.028),
            (WHEEL_R, t0), (tr(0.07), 0.07), (tr(0.105), 0.105), (tr(0.135), 0.135), (tr(0.135) - 0.012, 0.14), (0.38, 0.14), (0.37, 0.08),
            (0.21, 0.08), (0.20, 0.17), (0.10, 0.17)]
TREAD_SEG = {9, 10, 11}   # profile segments that are the running tread (polished)
def wheelset(name, loc=(0, 0, 0), exag=False, ticks=True, seg=96):
    """Two wheels on one solid axle; wheelset local frame: axle along Y, centre at axle height. Shape key 'exag' = exaggerated taper."""
    bm_v, faces, idx = [], [], []; prof_r, prof_e = wheel_profile(REAL_TAPER), wheel_profile(EXAG_TAPER)
    ex_v = []
    for side in (-1, 1):
        base = len(bm_v); k = len(prof_r)
        for i in range(seg):
            a = 2 * math.pi * i / seg; c, s_ = math.cos(a), math.sin(a)
            for (r, y), (re, ye) in zip(prof_r, prof_e):
                yy = side * (BACK + y); bm_v.append((r * c, yy, r * s_)); ex_v.append((re * c, side * (BACK + ye), re * s_))
        for i in range(seg):
            for j in range(k):
                a_, b_ = base + i * k + j, base + i * k + (j + 1) % k; c_, d_ = base + ((i + 1) % seg) * k + (j + 1) % k, base + ((i + 1) % seg) * k + j
                faces.append((a_, b_, c_, d_) if side > 0 else (a_, d_, c_, b_)); idx.append(1 if j in TREAD_SEG else 0)
    ob = mesh_obj(name, bm_v, faces, [M["wheel"], M["tread"]], idx, smooth=True, sharp=30, loc=loc, normals=False)
    ob.shape_key_add(name="Basis"); kb = ob.shape_key_add(name="exag")
    for i, p in enumerate(ex_v): kb.data[i].co = p
    kb.value = 1.0 if exag else 0.0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.085, radius2=0.085, depth=2.0, matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
    for side in (-1, 1):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.12, radius2=0.12, depth=0.06, matrix=Matrix.Translation((0, side * 0.79, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    ax = bm_obj(name + "_axle", bm, [M["steel"]], smooth=True); ax.parent = ob
    if ticks:
        for side in (-1, 1):
            tk = box(f"{name}_tick{side}", (0, side * (BACK + 0.142), 0.36), (0.05, 0.004, 0.16), M["tick"]); tk.parent = ob
    return ob, kb

# ---------- bogie: frame, springs, dampers, two wheelsets ----------
def coil(name, c, r, h, turns, wire, m):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); n = int(turns * 24); sp.points.add(n - 1)
    for i, p_ in enumerate(sp.points):
        a = 2 * math.pi * turns * i / (n - 1); p_.co = (c[0] + r * math.cos(a), c[1] + r * math.sin(a), c[2] + h * i / (n - 1), 1)
    cu.bevel_depth = wire; cu.bevel_resolution = 3; cu.materials.append(m); return link(bpy.data.objects.new(name, cu))
def bogie(name, wb=2.9, exag=False, glow_dampers=False):
    root = link(bpy.data.objects.new(name, None)); parts = []; glows = []
    for sx in (-1, 1):
        ws, _ = wheelset(f"{name}_ws{sx}", exag=exag); ws.parent = root; ws.location = (sx * wb / 2, 0, AXLE_Z); parts.append(ws)
    for sy in (-1, 1):
        parts.append(box(f"{name}_side{sy}", (0, sy * 1.06, AXLE_Z + 0.42), (wb + 0.9, 0.14, 0.26), M["bogie"], bevel=0.02))
        for sx in (-1, 1):
            parts.append(box(f"{name}_abox{sx}{sy}", (sx * wb / 2, sy * 1.0, AXLE_Z), (0.34, 0.22, 0.3), M["bogie"], bevel=0.02))
            parts.append(coil(f"{name}_pspring{sx}{sy}", (sx * wb / 2, sy * 1.0, AXLE_Z + 0.15), 0.08, 0.15, 4, 0.015, M["spring"]))
        parts.append(coil(f"{name}_sspring{sy}", (0.0, sy * 1.0, AXLE_Z + 0.54), 0.16, 0.2, 3.5, 0.026, M["spring"]))
        for nm_, c_, s_ in ((f"{name}_vdamp{sy}", (0.45, sy * 1.25, AXLE_Z + 0.62), (0.08, 0.08, 0.3)), (f"{name}_yawdamp{sy}", (-0.3, sy * 1.3, AXLE_Z + 0.66), (0.75, 0.08, 0.08))):
            parts.append(box(nm_, c_, s_, M["damper"], bevel=0.02))
            if glow_dampers: g = no_light(box(nm_ + "_glow", c_, tuple(x + 0.05 for x in s_), M["green_glow"])); parts.append(g); glows.append(g)
    for sx in (-0.45, 0.45): parts.append(box(f"{name}_tran{sx}", (sx, 0, AXLE_Z + 0.42), (0.22, 2.0, 0.2), M["bogie"], bevel=0.02))
    parts.append(box(f"{name}_bolster", (0, 0, AXLE_Z + 0.8), (0.5, 2.3, 0.12), M["bogie"], bevel=0.02))
    for p_ in parts:
        if p_.parent is None: p_.parent = root
    root["glows"] = [g.name for g in glows]
    return root

# ---------- generic coach / loco bodies ----------
def body_section(w, z0, z1, roof=0.35, n=24):
    pts = [(-w, z0), (w, z0), (w, z1 - roof)]
    for i in range(1, n):
        a = math.pi * i / n; pts.append((w * math.cos(a), z1 - roof + roof * math.sin(a)))
    pts.append((-w, z1 - roof)); return pts
def coach(name, length=23.5, livery="coach"):
    root = link(bpy.data.objects.new(name, None)); prof = body_section(1.6, RAIL_Z + 1.35, RAIL_Z + 4.2)
    secs = []; k = len(prof)
    for x in (-length / 2, length / 2): secs.append([(x, u, v) for u, v in prof])
    v = secs[0] + secs[1]; f = [(j, (j + 1) % k, k + (j + 1) % k, k + j) for j in range(k)] + [tuple(range(k)), tuple(range(2 * k - 1, k - 1, -1))]
    b = mesh_obj(name + "_body", v, f, [M[livery]], smooth=True, sharp=30); b.parent = root
    for sy in (-1, 1):   # grey band, windows, doors
        g = box(f"{name}_band{sy}", (0, sy * 1.605, RAIL_Z + 1.9), (length - 0.2, 0.01, 0.6), M["coach_grey"]); g.parent = root
        for i in range(int((length - 5) / 1.55)):
            x = -length / 2 + 3.0 + i * 1.55
            w_ = box(f"{name}_win{sy}{i}", (x, sy * 1.607, RAIL_Z + 2.85), (1.0, 0.01, 0.75), M["glass"]); w_.parent = root
        for x in (-length / 2 + 1.2, length / 2 - 1.2):
            d = box(f"{name}_door{sy}{x}", (x, sy * 1.606, RAIL_Z + 2.5), (0.8, 0.012, 1.9), M["coach_grey"]); d.parent = root
    u = box(name + "_under", (0, 0, RAIL_Z + 1.2), (length - 8.5, 2.4, 0.3), M["dark"]); u.parent = root
    return root
def loco(name, length=20.0):
    root = coach(name, length, "loco")
    for sy in (-1, 1):
        s = box(f"{name}_stripe{sy}", (0, sy * 1.608, RAIL_Z + 1.6), (length - 0.2, 0.01, 0.25), plain("loco_red", (0.4, 0.03, 0.02), 0.35, coat=0.4)); s.parent = root
    ws = box(name + "_screen", (length / 2 + 0.005, 0, RAIL_Z + 3.3), (0.01, 2.4, 0.8), M["glass"]); ws.parent = root
    return root

# ---------- MAIN scene: long curved track on an embankment in grassland, trees, a moving train ----------
photo_sky(1.0)
track("main", 0.0, LTOT)
mesh_obj("ground", [(-1500, -1500, -0.42), (1500, -1500, -0.42), (1500, 1500, -0.42), (-1500, 1500, -0.42)], [(0, 1, 2, 3)], [M["grass"]], normals=False)
def tree(bm, x, y, s):
    r1 = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.25 * s, radius2=0.18 * s, depth=3 * s, matrix=Matrix.Translation((x, y, 1.1 * s)))
    for v in r1["verts"]:
        for f_ in v.link_faces: f_.material_index = 1
    for _ in range(3):
        o = Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0, 1.2))) * s
        r2 = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=random.uniform(1.4, 2.2) * s, matrix=Matrix.Translation((x + o.x, y + o.y, 3.6 * s + o.z)))
        for v in r2["verts"]:
            v.co += Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))) * 0.25 * s
            for f_ in v.link_faces: f_.material_index = 0
bm = bmesh.new(); placed = 0
while placed < 260:
    x, y = random.uniform(-350, 300), random.uniform(-300, 350)
    near = min((Vector((x, y, 0)) - path(s)[0]).length for s in range(0, int(LTOT), 6))
    if near < 14: continue
    tree(bm, x, y, random.uniform(1.6, 3.0)); placed += 1
bm_obj("trees", bm, [M["leaf"], M["bark"]], smooth=True)

CARS = [("loco", 20.0)] + [(f"coach{i}", 23.5) for i in range(4)]
train = []; before = set(bpy.data.objects)
for nm, ln in CARS:
    body = loco(nm, ln) if nm == "loco" else coach(nm, ln)
    bgs = [bogie(f"{nm}_bogie{j}", glow_dampers=(nm == "coach0" and j == 0)) for j in (0, 1)]
    train.append((body, bgs, ln))
TRAIN_OBJS = [o for o in bpy.data.objects if o not in before]
def place_train(s_front, frame):
    """Put every car on the path with its front at s_front, keyframe it, and roll the wheels."""
    s = s_front
    for body, bgs, ln in train:
        c = s - ln / 2; pb = [c + ln / 2 - 3.6, c - ln / 2 + 3.6]
        (p1, _), (p2, _) = path(pb[0]), path(pb[1]); mid = (p1 + p2) / 2; hd = math.atan2(p1.y - p2.y, p1.x - p2.x)
        body.location = mid; body.rotation_euler = (0, 0, hd); key(body, "location", frame, None, "LINEAR"); key(body, "rotation_euler", frame, None, "LINEAR")
        for bg, sb in zip(bgs, pb):
            p, h = path(sb); bg.location = p; bg.rotation_euler = (0, 0, h); key(bg, "location", frame, None, "LINEAR"); key(bg, "rotation_euler", frame, None, "LINEAR")
            for ch in bg.children:
                if "_ws" in ch.name and "tick" not in ch.name: ch.rotation_euler = (0, sb / WHEEL_R, 0); key(ch, "rotation_euler", frame, None, "LINEAR")
        s -= ln + 1.2
def run_train(sid, s_start, speed):
    a, b = span(sid)
    for fr in list(range(a, b + 1, 2)) + [b]: place_train(s_start + speed * (fr - a) / FPS, fr)

# ---------- S1: wheel on the curve (hook), slow ----------
a1, b1 = span("S1_wheel_question")
run_train("S1_wheel_question", L0 + 22, 2.5)
c1 = camera("c1_wheel", 26, None); fill_light(c1, 120)
fo1 = link(bpy.data.objects.new("c1_focus", None)); c1.data.dof.use_dof = True; c1.data.dof.aperture_fstop = 2.4; c1.data.dof.focus_object = fo1
SW1 = L0 + 22 - 20.0 + 3.6 + 1.45          # leading wheelset of the loco's rear bogie at the start of S1
for fr in list(range(a1, b1 + 1, 4)) + [b1]:
    sw = SW1 + 2.5 * (fr - a1) / FPS
    aim(c1, fr, frame_at(sw + 1.9, -1.75, 0.36)[0], frame_at(sw, -0.95, 0.5)[0], "LINEAR"); fo1.location = frame_at(sw, -0.95, 0.45)[0]; key(fo1, "location", fr, None, "LINEAR")

# ---------- S2: x-ray car on a road curve, then its differential ----------
a2, b2 = span("S2_car_diff"); RC = 16.0
def rpath(s): p = s / RC; return Vector((RC * math.sin(p), RC - RC * math.cos(p), 0)) + Z_CAR, p
sweep("road", -0.0, RC * math.radians(150), 0.4, [(-3.6, 0.0), (3.6, 0.0), (3.6, -0.05), (-3.6, -0.05)], 0, [M["asphalt"]], pathf=rpath)
for side in (-1, 1): sweep(f"road_line{side}", 0, RC * math.radians(150), 0.4, [(-0.06, 0.005), (0.06, 0.005), (0.06, 0.0), (-0.06, 0.0)], side * 3.3, [M["paint_white"]], pathf=rpath)
mesh_obj("car_ground", [(-80, -680, -0.06), (80, -680, -0.06), (80, -520, -0.06), (-80, -520, -0.06)], [(0, 1, 2, 3)], [M["grass"]], normals=False)
car = link(bpy.data.objects.new("car", None))
secs = []
for x in [-2.2 + 4.4 * i / 16 for i in range(17)]:
    t_ = (x + 2.2) / 4.4; w = 0.88 * (1 - 0.25 * (2 * t_ - 1) ** 6); top = 1.0 + 0.45 * math.exp(-((t_ - 0.45) / 0.22) ** 2)
    secs.append([(x, w * math.copysign(abs(math.cos(a)) ** 0.6, math.cos(a)), 0.3 + (top - 0.3) * (0.5 + 0.5 * math.copysign(abs(math.sin(a)) ** 0.6, math.sin(a)))) for a in [2 * math.pi * j / 32 for j in range(32)]])
cv = [p for s_ in secs for p in s_]; k = 32; cf = [(i * k + j, i * k + (j + 1) % k, (i + 1) * k + (j + 1) % k, (i + 1) * k + j) for i in range(len(secs) - 1) for j in range(k)]
cv += [(-2.2, 0, 0.62), (2.2, 0, 0.62)]; nlast = len(secs) - 1
cf += [(len(cv) - 2, (j + 1) % k, j) for j in range(k)] + [(len(cv) - 1, nlast * k + j, nlast * k + (j + 1) % k) for j in range(k)]
cb = mesh_obj("car_body", cv, cf, [M["xray"]], smooth=True, sharp=80); cb.parent = car; no_light(cb)
key(cb, "hide_render", 1, False); key(cb, "hide_render", F(SH["S2_car_diff"]["start"]) + int((F(SH["S2_car_diff"]["end"]) - F(SH["S2_car_diff"]["start"])) * 0.55), True)
wheels = {}
for sx in (-1, 1):
    for sy in (-1, 1):
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.32, radius2=0.32, depth=0.22, matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
        tw = bm_obj(f"tyre{sx}{sy}", bm, [M["rubber"]], smooth=True, loc=(sx * 1.35, sy * 0.78, 0.32)); tw.parent = car
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=0.2, radius2=0.2, depth=0.23, matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
        rm = bm_obj(f"rim{sx}{sy}", bm, [M["rim"]], smooth=True); rm.parent = tw
        box(f"spoke{sx}{sy}", (0, sy * 0.116, 0.1), (0.05, 0.005, 0.2), M["tick"], parent=tw)
        wheels[(sx, sy)] = tw
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.04, radius2=0.04, depth=1.4, matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
bm_obj("halfshafts", bm, [M["steel"]], smooth=True, loc=(-1.35, 0, 0.32)).parent = car
diff = link(bpy.data.objects.new("diff", None)); diff.parent = car; diff.location = (-1.35, 0, 0.32)
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.17)
hs = bm_obj("diff_housing", bm, [xray("diff_xray", (0.9, 0.6, 0.3), (1.0, 0.55, 0.15))], smooth=True); hs.parent = diff; no_light(hs)
ring = link(bpy.data.objects.new("ring_gear", None)); ring.parent = diff
bm = bmesh.new()
for i in range(30):
    a = 2 * math.pi * i / 30; bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Rotation(a, 4, "Y") @ Matrix.Translation((0, 0.05, 0.12)) @ Matrix.Diagonal((0.02, 0.03, 0.03, 1)))
bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.115, radius2=0.115, depth=0.03, matrix=Matrix.Translation((0, 0.05, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
bm_obj("ring_teeth", bm, [plain("gear_gold", (0.75, 0.5, 0.15), 0.3, metal=1.0)], smooth=False).parent = ring
for sy in (-1, 1):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.06, radius2=0.035, depth=0.05, matrix=Matrix.Translation((0, sy * 0.055, 0)) @ Matrix.Rotation(-sy * math.pi / 2, 4, "X"))
    bm_obj(f"side_gear{sy}", bm, [plain("gear_steel", (0.6, 0.6, 0.62), 0.3, metal=1.0)], smooth=True).parent = ring
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.04, radius2=0.025, depth=0.04, matrix=Matrix.Translation((0, 0, sy * 0.05)) @ Matrix.Rotation(0 if sy > 0 else math.pi, 4, "X"))
    bm_obj(f"spider{sy}", bm, [plain("gear_red", (0.6, 0.08, 0.05), 0.3, metal=0.8)], smooth=True).parent = ring
for fr in range(a2, b2 + 1, 2):
    t_ = (fr - a2) / FPS; s_ = 4.0 + 4.5 * t_; p, h = rpath(s_)
    car.location = p; car.rotation_euler = (0, 0, h); key(car, "location", fr, None, "LINEAR"); key(car, "rotation_euler", fr, None, "LINEAR")
    for (sx, sy), tw in wheels.items():
        rr = RC - sy * 0.78; tw.rotation_euler = (0, s_ * rr / RC / 0.32, 0); key(tw, "rotation_euler", fr, None, "LINEAR")
    ring.rotation_euler = (0, s_ / 0.32 * 0.25, 0); key(ring, "rotation_euler", fr, None, "LINEAR")
for sy, col in ((1, M["cyan_glow"]), (-1, M["orange_glow"])):   # inner (left, +y) and outer wheel paths draw on
    rr = RC - sy * 0.78; cu = bpy.data.curves.new(f"wpath{sy}", "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); n = 60; sp.points.add(n - 1)
    for i, p_ in enumerate(sp.points):
        ang = (4.0 - 1.35) / RC + (4.5 * (b2 - a2) / FPS) / RC * i / (n - 1); pp = Vector((rr * math.sin(ang), RC - rr * math.cos(ang), 0.02)) + Z_CAR; p_.co = (*pp, 1)
    cu.bevel_depth = 0.05; cu.bevel_factor_mapping_end = "SPLINE"; cu.materials.append(col); ob = no_light(link(bpy.data.objects.new(f"wpath{sy}", cu)))
    key(cu, "bevel_factor_end", 1, 0.0, "LINEAR"); key(cu, "bevel_factor_end", a2, 0.0, "LINEAR"); key(cu, "bevel_factor_end", b2, 1.0, "LINEAR")
c2 = camera("c2_car", 30)
mid2 = a2 + (b2 - a2) // 2
pc, _ = rpath(4.0 + 4.5 * (mid2 - a2) / FPS)
aim(c2, a2, Z_CAR + Vector((5.5, 1.5, 9.0)), Z_CAR + Vector((4.6, 1.6, 0.0))); aim(c2, mid2, Z_CAR + Vector((8.0, 3.0, 7.0)), pc)
pd, hd2 = rpath(4.0 + 4.5 * (b2 - a2) / FPS); Rz = Matrix.Rotation(hd2, 3, "Z")
aim(c2, b2, pd + Rz @ Vector((-3.0, 1.3, 1.0)), pd + Rz @ Vector((-1.35, 0, 0.32)))
callout = []
def ring_callout(name, center, radius, normal, col, f0, f1, hide=None):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); n = 64; sp.points.add(n)
    q = Vector(normal).to_track_quat("Z", "Y")
    for i, p_ in enumerate(sp.points): a = math.pi * 0.6 + 2 * math.pi * i / n; p_.co = (*(Vector(center) + q @ Vector((radius * math.cos(a), radius * math.sin(a), 0))), 1)
    cu.bevel_depth = radius * 0.035; cu.bevel_factor_mapping_end = "SPLINE"; cu.materials.append(col); ob = no_light(link(bpy.data.objects.new(name, cu)))
    key(cu, "bevel_factor_end", 1, 0.0, "LINEAR"); key(cu, "bevel_factor_end", f0, 0.0, "LINEAR"); key(cu, "bevel_factor_end", f1, 1.0, "LINEAR")
    if hide: key(ob, "hide_render", 1, False); key(ob, "hide_render", hide, True)
    return ob
rc1 = ring_callout("contact_callout", (0, 0, 0), 0.2, (0, 1, 0), M["red_glow"], a1 + 34, a1 + 48, hide=b1 + 1)   # S1: wheel-rail contact
rc1.parent = train[0][1][1]; rc1.location = (1.45, -(BACK + 0.07), RAIL_Z)
rc = ring_callout("diff_callout", (0, 0, 0), 0.3, (0, 0, 1), M["red_glow"], mid2 + 10, mid2 + 24); rc.parent = diff; rc.rotation_euler = (math.pi / 2, 0, 0)

# ---------- S3: wheelset on a stand (sync), then the curve from above (outer rail longer) ----------
a3, b3 = span("S3_axle_and_curve"); m3 = a3 + int((b3 - a3) * 0.5)
mesh_obj("stand_floor", [(-30, 570, 0), (30, 570, 0), (30, 640, 0), (-30, 640, 0)], [(0, 1, 2, 3)], [M["sleeper"]], normals=False)
for sy in (-1, 1): box(f"stand{sy}", Z_STAND + Vector((0, sy * 1.0, 0.35)), (0.5, 0.4, 0.7), M["sleeper"], bevel=0.02)
ws3, _ = wheelset("ws_stand", loc=Z_STAND + Vector((0, 0, 0.82)))
key(ws3, "rotation_euler", 1, Vector((0, 0, 0)), "LINEAR"); key(ws3, "rotation_euler", N, Vector((0, 2 * math.pi * 0.5 * N / FPS, 0)), "LINEAR")
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.1, radius2=0.1, depth=1.5, matrix=Matrix.Rotation(math.pi / 2, 4, "X"))
ag = no_light(bm_obj("axle_glow", bm, [M["cyan_glow"]], smooth=True, loc=Z_STAND + Vector((0, 0, 0.82))))
key(ag, "scale", 1, Vector((0.001, 0.001, 0.001))); key(ag, "scale", a3 + 10, Vector((0.001, 1, 0.001))); key(ag, "scale", a3 + 22, Vector((1, 1, 1)))
c3 = camera("c3_stand", 40, Z_STAND + Vector((0, 0, 0.82)), 4.0)
aim(c3, a3, Z_STAND + Vector((3.3, -1.9, 1.6)), Z_STAND + Vector((0, 0, 0.8))); aim(c3, m3, Z_STAND + Vector((2.9, -1.4, 1.35)), Z_STAND + Vector((0, 0, 0.8)))
c3b = camera("c3_top", 35)
cs = path(L0 + R * ARC / 2)[0]
aim(c3b, m3 + 1, Vector((38, 50, 128)), Vector((40, 54, 0))); aim(c3b, b3, Vector((39, 52, 118)), Vector((40, 54, 0)))
for side, col in ((1, M["cyan_glow"]), (-1, M["orange_glow"])):   # inner (left) rail cyan, outer (right) rail orange, drawn over the arc
    cu = bpy.data.curves.new(f"railglow{side}", "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); n = 90; sp.points.add(n - 1)
    for i, p_ in enumerate(sp.points): p_.co = (*frame_at(L0 + R * ARC * i / (n - 1), side * HALF_G, RAIL_Z + 0.06)[0], 1)
    cu.bevel_depth = 0.6; cu.bevel_factor_mapping_end = "SPLINE"; cu.materials.append(col); rg = no_light(link(bpy.data.objects.new(f"railglow{side}", cu)))
    key(rg, "hide_render", 1, False); key(rg, "hide_render", b3 + 1, True)
    key(cu, "bevel_factor_end", 1, 0.0, "LINEAR"); key(cu, "bevel_factor_end", m3 + 6, 0.0, "LINEAR"); key(cu, "bevel_factor_end", b3 - 10, 1.0, "LINEAR")

# ---------- S4: wheel cross-section (taper exaggerated) ----------
a4, b4 = span("S4_cone")
X4 = Z_STAND + Vector((12, 0, 1.6))   # lifted clear of the floor and ground
mesh_obj("backdrop4", [(3, -3, -3), (3, 4, -3), (3, 4, 3), (3, -3, 3)], [(0, 1, 2, 3)], [M["backdrop"]], loc=X4, normals=False)
def slice_obj(name, pts_r, pts_e, m, loc):
    """Thin extrusion (along X) of a 2D outline given as (y, z) points; shape key 'exag' moves it to pts_e."""
    k = len(pts_r); v = [(-0.03, y, z) for y, z in pts_r] + [(0.03, y, z) for y, z in pts_r]
    f = [tuple(range(k)), tuple(range(2 * k - 1, k - 1, -1))] + [(j, (j + 1) % k, k + (j + 1) % k, k + j) for j in range(k)]
    ob = mesh_obj(name, v, f, [m], loc=loc, normals=True); ob.shape_key_add(name="Basis"); kb = ob.shape_key_add(name="exag")
    for i, (y, z) in enumerate(pts_e + pts_e): kb.data[i].co = (-0.03 if i < k else 0.03, y, z)
    return ob, kb
wy = lambda prof: [(BACK + y, -r) for r, y in prof]                    # wheel outline: y outward, z = -radius (bottom of the wheel)
sl, kb4 = slice_obj("wheel_slice", wy(wheel_profile(REAL_TAPER)), wy(wheel_profile(EXAG_TAPER)), plain("slice_cut", (0.74, 0.75, 0.77), 0.45, metal=0.2, emit=(0.74, 0.75, 0.77), estr=0.55), X4)
key(kb4, "value", 1, 0.0); key(kb4, "value", a4 + 12, 0.0); key(kb4, "value", a4 + 40, 1.0)
ghost, gkb = wheelset("ws_ghost", loc=X4, ticks=False)   # faint x-ray wheel around the section, so it reads as a wheel
ghost.data.materials[0] = M["xray"]; ghost.data.materials[1] = M["xray"]; no_light(ghost)
for ch in ghost.children: ch.hide_render = True
key(ghost, "hide_render", 1, False); key(ghost, "hide_render", a4 + 30, True)   # fades out once the camera reaches the side view
key(gkb, "value", 1, 0.0); key(gkb, "value", a4 + 12, 0.0); key(gkb, "value", a4 + 40, 1.0)
rail_pts = [(HALF_G + u, v - RAIL_Z - WHEEL_R) for u, v in RAIL_P]   # rail head top at z = -WHEEL_R (touching the tread)
slice_obj("rail_slice", rail_pts, rail_pts, plain("rail_cut", (0.36, 0.34, 0.32), 0.5, metal=0.3, emit=(0.4, 0.36, 0.33), estr=0.35), X4)
cu = bpy.data.curves.new("slope_line", "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); sp.points.add(1)
pe = wheel_profile(EXAG_TAPER); (r0, y0), (r1, y1) = pe[9], pe[12]
sp.points[0].co = (-0.05, BACK + y0, -r0 - 0.008, 1); sp.points[1].co = (-0.05, BACK + y1, -r1 - 0.008, 1)
cu.bevel_depth = 0.004; cu.materials.append(M["orange_glow"]); sline = no_light(link(bpy.data.objects.new("slope_line", cu))); sline.location = X4
key(sline, "hide_render", 1, True); key(sline, "hide_render", a4 + 42, False)
ring_callout("slope_callout", X4 + Vector((-0.06, BACK + 0.09, -WHEEL_R - 0.004)), 0.055, (1, 0, 0), M["red_glow"], a4 + 50, a4 + 66)
c4 = camera("c4_slice", 85)
aim(c4, a4, X4 + Vector((-1.9, BACK - 1.5, 0.15)), X4 + Vector((0, BACK + 0.09, -0.22))); aim(c4, a4 + 34, X4 + Vector((-2.2, BACK + 0.09, -WHEEL_R + 0.13)), X4 + Vector((0, BACK + 0.09, -WHEEL_R + 0.13)))
aim(c4, b4, X4 + Vector((-1.8, BACK + 0.09, -WHEEL_R + 0.1)), X4 + Vector((0, BACK + 0.09, -WHEEL_R + 0.1)))
lt = link(bpy.data.objects.new("slice_key", bpy.data.lights.new("slice_key", "AREA"))); lt.data.energy = 220; lt.data.size = 1.5; lt.location = X4 + Vector((-1.2, BACK - 0.4, 0.3))
lt.rotation_euler = (X4 + Vector((0, BACK + 0.09, -WHEEL_R)) - lt.location).to_track_quat("-Z", "Y").to_euler()

# ---------- S5: exaggerated wheelset on the curve shifts outward; rolling circles; distance bars ----------
a5, b5 = span("S5_shift")
ws5, _ = wheelset("ws_curve", exag=True)
S5 = L0 + 40.0; shift = 0.045
for fr in range(a5, b5 + 1, 2):
    t_ = (fr - a5) / (b5 - a5); s_ = S5 + 3.0 * t_; lat = -shift * min(1.0, t_ / 0.25)
    p, h = frame_at(s_, lat, AXLE_Z); ws5.location = p; ws5.rotation_euler = (0, s_ / WHEEL_R, h); key(ws5, "location", fr, None, "LINEAR"); key(ws5, "rotation_euler", fr, None, "LINEAR")
key(ws5, "hide_render", 1, True); key(ws5, "hide_render", a5, False); key(ws5, "hide_render", b5 + 1, True)
for side, col, dr in ((1, M["cyan_glow"], -shift * EXAG_TAPER), (-1, M["orange_glow"], shift * EXAG_TAPER)):   # rolling circle on each wheel
    r0 = WHEEL_R + dr
    cu = bpy.data.curves.new(f"rollc{side}", "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); sp.points.add(96); sp.use_cyclic_u = True
    for i, p_ in enumerate(sp.points): a = 2 * math.pi * i / 96; p_.co = (r0 * math.cos(a), side * (BACK + 0.075), r0 * math.sin(a), 1)
    cu.bevel_depth = 0.008; cu.materials.append(col); rco = no_light(link(bpy.data.objects.new(f"rollc_{side}", cu))); rco.parent = ws5
    key(rco, "hide_render", 1, True); key(rco, "hide_render", a5 + 30, False)
for side, col, rr in ((1, M["cyan_glow"], WHEEL_R - shift * EXAG_TAPER), (-1, M["orange_glow"], WHEEL_R + shift * EXAG_TAPER)):   # distance per turn
    cu = bpy.data.curves.new(f"dist{side}", "CURVE"); cu.dimensions = "3D"; sp = cu.splines.new("POLY"); n = 40; sp.points.add(n - 1)
    ln = 2 * math.pi * rr * 0.55
    for i, p_ in enumerate(sp.points): p_.co = (*frame_at(S5 + 3.0 + ln * i / (n - 1), side * HALF_G - (shift if side < 0 else -0.0), RAIL_Z + 0.03)[0], 1)
    cu.bevel_depth = 0.035; cu.bevel_factor_mapping_end = "SPLINE"; cu.materials.append(col); no_light(link(bpy.data.objects.new(f"dist_{side}", cu)))
    key(cu, "bevel_factor_end", 1, 0.0, "LINEAR"); key(cu, "bevel_factor_end", a5 + 70, 0.0, "LINEAR"); key(cu, "bevel_factor_end", b5 - 14, 1.0, "LINEAR")
c5 = camera("c5_shift", 35)
pA, hA = frame_at(S5 + 1.5, 0, 0)
aim(c5, a5, frame_at(S5 + 4.3, -1.6, 2.3)[0], frame_at(S5 + 1.2, -0.25, 0.75)[0]); aim(c5, b5, frame_at(S5 + 6.5, -1.2, 2.1)[0], frame_at(S5 + 4.2, -0.3, 0.6)[0])

# ---------- S6: bogie rolls round the curve ----------
a6, b6 = span("S6_bogie")
run_train("S6_bogie", L0 + 70, 9.0)
c6 = camera("c6_bogie", 24); fill_light(c6, 160)
sb = L0 + 70 - 20.0 - 1.2 - 23.5 / 2 + 23.5 / 2 - 3.6
for fr in list(range(a6, b6 + 1, 4)) + [b6]:
    sbb = sb + 9.0 * (fr - a6) / FPS
    aim(c6, fr, frame_at(sbb + 2.2, -4.6, 0.95)[0], frame_at(sbb + 0.3, 0, 0.8)[0], "LINEAR")

# ---------- S7: hunting on a straight track (exaggerated sway) ----------
a7, b7 = span("S7_hunting")
def hpath(s): return Vector((s - 200.0, 0, 0)) + Z_HUNT, 0.0
track("hunt", 0.0, 420.0, pathf=hpath)
hb = bogie("hunt_bogie"); V7 = 38.0
for fr in range(a7, b7 + 1):
    t_ = (fr - a7) / FPS; x = -60 + V7 * t_; amp = 0.055 * min(1.0, max(0.0, (t_ - 1.2) / 2.0)); ph = 2 * math.pi * 1.7 * t_
    hb.location = Z_HUNT + Vector((x, amp * math.sin(ph), 0)); hb.rotation_euler = (0, 0, amp * 0.9 * math.cos(ph))
    key(hb, "location", fr, None, "LINEAR"); key(hb, "rotation_euler", fr, None, "LINEAR")
    for ch in hb.children:
        if "_ws" in ch.name: ch.rotation_euler = (0, (x + 60) / WHEEL_R, 0); key(ch, "rotation_euler", fr, None, "LINEAR")
for sy in (-1, 1):
    fl = ring_callout(f"flange_flash{sy}", (0, 0, 0), 0.55, (0, 1, 0), M["red_glow"], a7 + 40, a7 + 52)
    fl.parent = hb; fl.location = (1.45, sy * 0.82, AXLE_Z)
c7 = camera("c7_hunt", 24)
for fr in range(a7, b7 + 1, 6):
    t_ = (fr - a7) / FPS; x = -60 + V7 * t_
    aim(c7, fr, Z_HUNT + Vector((x + 4.6, -2.3, 1.25)), Z_HUNT + Vector((x + 0.4, 0, 0.72)), "LINEAR")

# ---------- S8: steady modern bogie (dampers glow), pull back to the train on the curve ----------
a8, b8 = span("S8_train_wide")
run_train("S8_train_wide", L0 + 95, 11.0)
c8 = camera("c8_wide", 26); fill_light(c8, 160)
s8 = L0 + 95 - 20.0 - 1.2 - 3.6          # coach0 front bogie at the start of S8
for fr in list(range(a8, b8 + 1, 4)) + [b8]:
    t_ = (fr - a8) / (b8 - a8); sb8 = s8 + 11.0 * (fr - a8) / FPS; e = t_ * t_ * (3 - 2 * t_)
    loc = frame_at(sb8 + 2.0 + 22 * e, -4.4 - 58 * e, 0.95 + 24 * e)[0]; tgt = frame_at(sb8 + 0.3 - 18 * e, 0.0 + 4 * e, 0.8 + 1.1 * e)[0]
    aim(c8, fr, loc, tgt, "LINEAR")
for g in train[1][1][0]["glows"]:
    ob = bpy.data.objects[g]; key(ob, "hide_render", 1, True); key(ob, "hide_render", a8, False)
for o in TRAIN_OBJS:   # the train only appears in S1, S6 and S8
    for fr, hid in ((1, False), (b1 + 1, True), (a6, False), (b6 + 1, True), (a8, False)): o.hide_render = hid; o.keyframe_insert("hide_render", frame=fr)
for g in train[1][1][0]["glows"]:
    ob = bpy.data.objects[g]; ob.animation_data_clear(); key(ob, "hide_render", 1, True); key(ob, "hide_render", a8, False)

# ---------- cameras on the timeline ----------
for fr, c in [(a1, c1), (a2, c2), (a3, c3), (m3 + 1, c3b), (a4, c4), (a5, c5), (a6, c6), (a7, c7), (a8, c8)]:
    sc.timeline_markers.new(c.name, frame=fr).camera = c
sc.camera = c1
cycles(32)
render(os.path.join(HERE, "frames"), os.path.join(HERE, "scene.blend"))
