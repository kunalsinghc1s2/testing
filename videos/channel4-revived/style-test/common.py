"""Shared parts of the style test v2: the same shots, timing, cameras and base shapes for both looks (SCRIPT.md).
Each look file (look_a1.py realistic, look_a2.py toy low-poly) adds its own materials, world, props and diagrams.
Exterior plane at the origin (nose +X, camera side -Y); cabin cutaway at Z2; window panel at Z3."""
import bpy, bmesh, math, os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
N_FR = 360
Z2, Z3 = Vector((0, 300, 0)), Vector((0, 600, 0))
AX, AZ, NSQ = 0.6, 0.75, 24                 # window half-width, half-height; superellipse exponent for "square"
CRACK = [(0.58, 0.73), (0.7, 0.83), (0.76, 0.92), (0.9, 1.0), (0.97, 1.12), (1.1, 1.18), (1.18, 1.32), (1.33, 1.38),
         (1.42, 1.53), (1.58, 1.6), (1.68, 1.76), (1.85, 1.83)]
HEAT = [(145, 0), (158, 0), (176, 1.0), (186, 0.55), (196, 1.0), (206, 0.55), (216, 1.0)]   # stress "flights" pulse
MORPH = [(262, 0.0), (292, 1.0)]                                                          # square -> round
PULSE = [(61, 0.0, 1.0), (64, 0.0, 1.0), (74, 1.0, 1.0), (82, 1.0, 1.0), (94, 1.15, 1.07), (106, 1.0, 1.0),
         (118, 1.15, 1.07), (130, 1.0, 1.0), (142, 1.15, 1.07)]   # cutaway: (frame, arrow length, body radius)

def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = 24; sc.frame_start, sc.frame_end = 1, N_FR
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = int(os.environ.get("PCT", "100"))
    return sc

def key(obj, path, frame, value=None, interp="BEZIER"):
    bpy.context.preferences.edit.keyframe_new_interpolation_type = interp
    if value is not None: setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)

def link(ob): bpy.context.scene.collection.objects.link(ob); return ob

def mesh_obj(name, verts, faces, mats=(), idx=None, smooth=False, sharp=35, loc=(0, 0, 0), normals=True):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    if normals:
        bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    if idx is not None:
        for p, i in zip(me.polygons, idx): p.material_index = i
    if smooth: me.shade_smooth(); me.set_sharp_from_angle(angle=math.radians(sharp))
    else: me.shade_flat()
    ob = bpy.data.objects.new(name, me); ob.location = loc; return link(ob)

def bm_obj(name, bm, mats=(), smooth=False, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    me.shade_smooth() if smooth else me.shade_flat()
    ob = bpy.data.objects.new(name, me); ob.location = loc; return link(ob)

def bsdf_of(m): return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")

def superellipse(ax, az, n, k):
    """k points on |x/ax|^n + |z/az|^n = 1 (n=2 oval, n>=20 square with tiny corner radius)."""
    pts = []
    for i in range(k):
        t = 2 * math.pi * i / k; c, s = math.cos(t), math.sin(t)
        r = (abs(c / ax) ** n + abs(s / az) ** n) ** (-1.0 / n); pts.append((r * c, r * s))
    return pts

BOX_F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
def box(name, c, s, m, loc=(0, 0, 0), bevel=0.0):
    cx, cy, cz = c; sx, sy, sz = (a / 2 for a in s)
    ob = mesh_obj(name, [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)], BOX_F, [m], loc=loc)
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 3; md.harden_normals = True; ob.data.shade_smooth()
    return ob

# ---------- the plane ----------
def prof(x):
    if x > 10: u = (x - 10) / 5.0; return 2.0 * math.sqrt(max(0.0, 1 - u * u)), -0.25 * u * u
    if x < -10: u = (-10 - x) / 7.0; return 0.25 + 1.75 * (1 - u) ** 1.3, 1.5 * u ** 1.6
    return 2.0, 0.0

def fuselage(nseg, low, mats, belly_idx=None):
    nose = [10 + 5 * math.cos(t) for t in ([0.45, 0.95, 1.3] if low else [0.06 + i * (math.pi / 2 - 0.06) / 23 for i in range(24)])]
    mid = [10, -10] if low else [10 - 20 * i / 12 for i in range(1, 12)]
    tail = [-10 - 7 * u for u in ([0.0, 0.4, 0.75, 1.0] if low else [i / 24 for i in range(25)])]
    xs = sorted(set(round(x, 4) for x in nose + mid + tail), reverse=True)
    v = [(15.0, 0.0, -0.25)]
    for x in xs:
        r, zc = prof(x)
        for k in range(nseg):
            a = 2 * math.pi * k / nseg; v.append((x, -r * math.cos(a), zc + r * math.sin(a)))
    v.append((-17.12, 0.0, 1.5)); last = len(v) - 1; f = []
    R = lambda i, k: 1 + i * nseg + k % nseg
    for k in range(nseg): f.append((0, R(0, k + 1), R(0, k)))
    for i in range(len(xs) - 1):
        for k in range(nseg): f.append((R(i, k), R(i, k + 1), R(i + 1, k + 1), R(i + 1, k)))
    n = len(xs) - 1
    for k in range(nseg): f.append((last, R(n, k), R(n, k + 1)))
    idx = [belly_idx(sum(v[j][2] for j in face) / len(face)) for face in f] if belly_idx else None
    return mesh_obj("fuselage", v, f, mats, idx, smooth=not low, sharp=60)

def on_skin(x0, phi0, side, pts, h, low, nseg):
    """Map flat 2D points (u along x, w up the side) onto the skin at (x0, phi0); side -1 = camera side."""
    out = []
    for u, w in pts:
        if low:   # flat facet (facet centres at 15 + 30k deg for 12 segments)
            rf = 2.0 * math.cos(math.pi / nseg) + h
            y, z = -rf * math.cos(phi0) + w * math.sin(phi0), rf * math.sin(phi0) + w * math.cos(phi0)
        else:
            p = phi0 + w / 2.0; y, z = -(2.0 + h) * math.cos(p), (2.0 + h) * math.sin(p)
        out.append((x0 + u, -y if side > 0 else y, z))
    return out

def windows(low, nseg, m_glass, m_frame=None, frame_scale=(1.32, 1.25), doors=True):
    gv, gf, fv, ff = [], [], [], []
    phi = math.radians(15 if low else 12); k = 8 if low else 28
    glass = [(z, x) for x, z in (superellipse(0.18, 0.13, 2.4, k) if low else superellipse(0.17, 0.12, 2.6, k))]
    frame = [(u * frame_scale[0], w * frame_scale[1]) for u, w in glass]
    for side in (-1, 1):
        for i in range(33):
            x0 = -8.48 + 0.53 * i
            b = len(gv); gv += on_skin(x0, phi, side, glass, 0.012, low, nseg); gv.append(tuple(sum(c) / k for c in zip(*gv[b:b + k])))
            gf += [(b + j, b + (j + 1) % k, b + k) for j in range(k)]
            if m_frame:
                b = len(fv); fv += on_skin(x0, phi, side, frame, 0.006, low, nseg) + on_skin(x0, phi, side, glass, 0.006, low, nseg)
                ff += [(b + j, b + (j + 1) % k, b + k + (j + 1) % k, b + k + j) for j in range(k)]
        if m_frame and doors and not low:
            for x0 in (9.55, -9.6):
                o, ins = superellipse(0.46, 0.92, 6, 40), superellipse(0.43, 0.89, 6, 40)
                b = len(fv); fv += on_skin(x0, 0.0, side, o, 0.004, low, nseg) + on_skin(x0, 0.0, side, ins, 0.004, low, nseg)
                ff += [(b + j, b + (j + 1) % 40, b + 40 + (j + 1) % 40, b + 40 + j) for j in range(40)]
    mesh_obj("windows", gv, gf, [m_glass], normals=False, smooth=not low, sharp=80)
    if fv: mesh_obj("frames", fv, ff, [m_frame], normals=False)
    cv, cf = [], []; xs = [12.7 + 0.2 * i for i in range(9)]; ph = [math.radians(5 + 170 * j / 34) for j in range(35)]
    def np_(x, p):
        r, zc = prof(x); r += 0.012; return (x, -r * math.cos(p), zc + r * math.sin(p))
    for i in range(len(xs) - 1):
        for j in range(len(ph) - 1):
            q = [np_(xs[i], ph[j]), np_(xs[i + 1], ph[j]), np_(xs[i + 1], ph[j + 1]), np_(xs[i], ph[j + 1])]
            zc = sum(p[2] for p in q) / 4
            if 0.38 < zc < 0.9 and not abs(sum(p[1] for p in q) / 4) < 0.05:
                b = len(cv); cv += q; cf.append((b, b + 1, b + 2, b + 3))
    mesh_obj("cockpit", cv, cf, [m_glass], normals=False)

def airfoil(thick, low):
    if low: return [(0.0, 0.0), (0.3, thick * 0.6), (1.0, 0.0), (0.3, -thick * 0.6)]
    n = 14; xs = [0.5 * (1 - math.cos(math.pi * i / n)) for i in range(n + 1)]
    yt = lambda x: 5 * thick * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    return [(x, yt(x)) for x in xs] + [(x, -yt(x)) for x in reversed(xs[1:-1])]

def loft(name, sections, m, low):
    k = len(sections[0]); v = [p for s in sections for p in s]; f = []
    for i in range(len(sections) - 1):
        for j in range(k): f.append((i * k + j, i * k + (j + 1) % k, (i + 1) * k + (j + 1) % k, (i + 1) * k + j))
    f += [tuple(range(k)), tuple(range((len(sections) - 1) * k, len(sections) * k))]
    return mesh_obj(name, v, f, [m], smooth=not low, sharp=40)

def surface(name, root, tip, m, low, vertical=False, mirror=True, n_sec=8):
    """root/tip = (le_x, span_y, z, chord, thick); vertical surfaces span along z."""
    secs = []
    for s in ([0, 1] if low else [i / (n_sec - 1) for i in range(n_sec)]):
        le, sp, zz, ch, th = [a + (b - a) * s for a, b in zip(root, tip)]
        secs.append([(le - c * ch, t * ch, zz) if vertical else (le - c * ch, sp, zz + t * ch) for c, t in airfoil(th, low)])
    loft(name, secs, m, low)
    if mirror: loft(name + "_r", [[(x, -y, z) for x, y, z in s] for s in secs], m, low)

NAC = [(4.2, 0.82), (4.0, 0.93), (3.2, 0.98), (1.6, 0.92), (0.4, 0.74), (-0.3, 0.55)]
def nacelle(y0, m_body, m_pylon, low):
    k = 8 if low else 48; v = []; f = []
    for x, r in NAC:
        for j in range(k): a = 2 * math.pi * j / k; v.append((x, y0 + r * math.cos(a), -2.15 + r * math.sin(a)))
    for i in range(len(NAC) - 1):
        for j in range(k): f.append((i * k + j, i * k + (j + 1) % k, (i + 1) * k + (j + 1) % k, (i + 1) * k + j))
    v.append((-0.9, y0, -2.15)); c = len(v) - 1; n = len(NAC) - 1
    f += [(n * k + j, n * k + (j + 1) % k, c) for j in range(k)]
    mesh_obj(f"nacelle{y0}", v, f, [m_body], smooth=not low, sharp=50, normals=False)
    box(f"pylon{y0}", (1.6, y0, -1.07), (2.4, 0.24, 0.45), m_pylon)

def plane_shell(M, low):
    """Fuselage, windows, wings, tail and nacelles. M: material dict (paint, [belly], glass, [frame], wing, stab, fin, nacelle, pylon)."""
    nseg = 12 if low else 72
    if "belly" in M: fuselage(nseg, low, [M["paint"], M["belly"]], lambda z: 1 if z < -1.05 else 0)
    else: fuselage(nseg, low, [M["paint"]])
    windows(low, nseg, M["glass"], M.get("frame"))
    surface("wing", (4.5, 1.0, -1.25, 6.5, 0.13), (-3.0, 17.0, 0.15, 1.5, 0.10), M["wing"], low)
    surface("stab", (-13.4, 0.4, 0.95, 3.2, 0.10), (-16.4, 6.3, 1.35, 1.2, 0.09), M["stab"], low)
    surface("fin", (-10.4, 0.0, 1.0, 5.2, 0.10), (-15.3, 0.0, 7.3, 2.0, 0.09), M["fin"], low, vertical=True, mirror=False)
    for y0 in (6.0, -6.0): nacelle(y0, M["nacelle"], M["pylon"], low)
    return nseg

# ---------- cutaway shell (layers: list of (r_out, r_in, material for the cut face)) ----------
def cut_shell(nseg, m_outer, m_inner, layers, length=6.0):
    v, f, idx = [], [], []; mats = [m_outer, m_inner] + [l[2] for l in layers]
    radii = [layers[0][0]] + [l[1] for l in layers]          # outer skin radius, then each layer's inner radius
    for x in (0.0, -length):
        for r in radii:
            for j in range(nseg): a = 2 * math.pi * j / nseg; v.append((x, -r * math.cos(a), r * math.sin(a)))
    nr = len(radii); B = lambda xi, ri, j: (xi * nr + ri) * nseg + j % nseg
    for j in range(nseg):
        f.append((B(0, 0, j), B(1, 0, j), B(1, 0, j + 1), B(0, 0, j + 1))); idx.append(0)
        f.append((B(0, nr - 1, j), B(0, nr - 1, j + 1), B(1, nr - 1, j + 1), B(1, nr - 1, j))); idx.append(1)
        for li in range(nr - 1):
            f.append((B(0, li, j), B(0, li, j + 1), B(0, li + 1, j + 1), B(0, li + 1, j))); idx.append(2 + li)
            f.append((B(1, li, j), B(1, li + 1, j), B(1, li + 1, j + 1), B(1, li, j + 1))); idx.append(2 + li)
    return mesh_obj("shell", v, f, mats, idx, smooth=nseg > 20, sharp=50, loc=Z2)

def pulse_shell(shell):
    for fr, _, s in PULSE: key(shell, "scale", fr, Vector((1, s, s)))

def radial(j, n=12, start=15):
    a = math.radians(start + 360 / n * j); return Vector((0, -math.cos(a), math.sin(a)))

def seat_slots():
    """(x, y) of each seat in the cutaway: 6 rows x 6 seats facing +X (towards the camera)."""
    return [(-0.55 - 0.85 * row, y) for row in range(6) for y in (-1.45, -0.95, -0.45, 0.45, 0.95, 1.45)]

# ---------- window panel ----------
def r_in(t, n): c, s = math.cos(t), math.sin(t); return (abs(c / AX) ** n + abs(s / AZ) ** n) ** (-1.0 / n)

def plate(m, n_ang, n_ring, outer=3.4, smooth=True):
    """Skin panel with a window hole at Z3 (XZ plane). Shape key "round" morphs the square hole to an oval.
    Point attributes: s_sq / s_rd = stress (0..1) for the square / round hole; also returns the hole-edge vertex rings."""
    corner = math.atan2(AZ, AX)
    angs = sorted(set([2 * math.pi * i / n_ang for i in range(n_ang)] + [corner, math.pi - corner, math.pi + corner, 2 * math.pi - corner]))
    cpts = [(sx * AX * 2 ** (-1 / NSQ), sz * AZ * 2 ** (-1 / NSQ)) for sx in (-1, 1) for sz in (-1, 1)]
    pv, pv_rd, s_sq, s_rd = [], [], [], []
    for t in angs:
        ro = outer / max(abs(math.cos(t)), abs(math.sin(t)))
        for j in range(n_ring + 1):
            q = (j / n_ring) ** 1.8
            for n, out in ((NSQ, pv), (2, pv_rd)):
                ri = r_in(t, n); r = ri + q * (ro - ri); x, z = r * math.cos(t), r * math.sin(t); out.append((x, 0.0, z))
                dh = r - ri
                if n == NSQ: s_sq.append(min(1.0, math.exp(-min(math.hypot(x - cx, z - cz) for cx, cz in cpts) / 0.32) + 0.18 * math.exp(-dh / 0.3)))
                else: s_rd.append(0.36 * math.exp(-dh / 0.4) + 0.04)
    pf = []; NA = len(angs)
    for i in range(NA):
        for j in range(n_ring): a, b = i * (n_ring + 1) + j, ((i + 1) % NA) * (n_ring + 1) + j; pf.append((a, b, b + 1, a + 1))
    ob = mesh_obj("plate", pv, pf, [m], smooth=smooth, sharp=80, loc=Z3, normals=False)
    for nm, vals in (("s_sq", s_sq), ("s_rd", s_rd)):
        at = ob.data.attributes.new(nm, "FLOAT", "POINT"); at.data.foreach_set("value", vals)
    ob.shape_key_add(name="Basis"); kb = ob.shape_key_add(name="round")
    for i, p in enumerate(pv_rd): kb.data[i].co = p
    for fr, val in MORPH: key(kb, "value", fr, val)
    return ob, angs

def hole_ring(name, angs, m, inset, depth, n_sq=NSQ):
    """A ring just inside the hole edge (window seal / frame), shape-keyed with the panel's morph."""
    def ring(n):
        o, i_ = [], []
        for t in angs:
            ri = r_in(t, n); c, s = math.cos(t), math.sin(t)
            o.append((ri * c, depth * 0.3, ri * s)); i_.append(((ri - inset) * c, depth, (ri - inset) * s))
        return o + i_
    k = len(angs); sq, rd = ring(n_sq), ring(2)
    ob = mesh_obj(name, sq, [(j, (j + 1) % k, k + (j + 1) % k, k + j) for j in range(k)], [m], smooth=True, sharp=80, loc=Z3, normals=False)
    ob.shape_key_add(name="Basis"); kb = ob.shape_key_add(name="round")
    for i, p in enumerate(rd): kb.data[i].co = p
    for fr, val in MORPH: key(kb, "value", fr, val)
    return ob

def crack_curve(m, depth, frames=(204, 246), branches=()):
    objs = []
    for bi, pts in enumerate([CRACK] + list(branches)):
        cu = bpy.data.curves.new(f"crack{bi}", "CURVE"); cu.dimensions = "3D"; spl = cu.splines.new("POLY")
        spl.points.add(len(pts) - 1)
        for p_, (x, z) in zip(spl.points, pts): p_.co = (x, -0.012, z, 1)
        cu.bevel_depth = depth * (1 if bi == 0 else 0.6); cu.bevel_resolution = 2; cu.bevel_factor_mapping_end = "SPLINE"
        cu.materials.append(m)
        ob = link(bpy.data.objects.new(f"crack{bi}", cu)); ob.location = Z3
        f0, f1 = frames if bi == 0 else (frames[0] + 18 + 6 * bi, frames[1])
        key(cu, "bevel_factor_end", 1, 0.0, "LINEAR"); key(cu, "bevel_factor_end", f0, 0.0, "LINEAR"); key(cu, "bevel_factor_end", f1, 1.0, "LINEAR")
        key(ob, "hide_render", 1, False); key(ob, "hide_render", 256, True); objs.append(ob)
    return objs

# ---------- cameras (same in both looks) ----------
def cameras(dof):
    sc = bpy.context.scene
    def camera(name, lens, focus=None, fstop=2.8):
        c = link(bpy.data.objects.new(name, bpy.data.cameras.new(name))); c.data.lens = lens; c.data.clip_end = 60000
        if focus is not None and dof:
            fo = link(bpy.data.objects.new(name + "_focus", None)); fo.location = focus
            c.data.dof.use_dof = True; c.data.dof.focus_object = fo; c.data.dof.aperture_fstop = fstop
        return c
    def aim(c, frame, loc, tgt):
        loc = Vector(loc); key(c, "location", frame, loc); key(c, "rotation_euler", frame, (Vector(tgt) - loc).to_track_quat("-Z", "Y").to_euler())
    c1 = camera("c1_windows", 35, (2.6, -2.0, 0.42), 2.8)
    aim(c1, 1, (21, -15, -3.2), (3.5, -1.0, 0.9)); aim(c1, 60, (4.9, -3.5, 0.62), (2.3, -2.0, 0.5))
    c2 = camera("c2_cutaway", 35, Z2 + Vector((0.3, 0, 0)), 5.6)
    aim(c2, 61, Z2 + Vector((8.0, 1.6, 1.0)), Z2 + Vector((0, 0, 0.75))); aim(c2, 144, Z2 + Vector((7.5, -1.3, 0.9)), Z2 + Vector((0, 0, 0.75)))
    c3 = camera("c3_plate", 50, Z3, 4.0)
    for f, l, t in [(145, (0.5, -6.6, 0.75), (0.0, 0, 0.45)), (200, (0.25, -5.6, 0.6), (0.05, 0, 0.42)), (246, (0.75, -3.7, 1.05), (0.75, 0, 1.0)),
                    (262, (0.1, -5.9, 0.55), (0.0, 0, 0.42)), (324, (-0.15, -5.4, 0.5), (0.0, 0, 0.42))]:
        aim(c3, f, Z3 + Vector(l), Z3 + Vector(t))
    c5 = camera("c5_wide", 35)
    aim(c5, 325, (34, -40, -8), (6, 0, 1.0)); aim(c5, 360, (30, -42, -6.8), (6, 0, 1.0))
    for f, c in [(1, c1), (61, c2), (145, c3), (325, c5)]: sc.timeline_markers.new(c.name, frame=f).camera = c
    sc.camera = c1

def render(style):
    sc = bpy.context.scene; out = os.environ.get("OUT") or os.path.join(HERE, style, "frames"); os.makedirs(out, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, style, "scene.blend"))
    fr = os.environ.get("FRAMES", "")
    if fr and "-" not in fr:
        for f in [int(x) for x in fr.split(",")]:
            sc.frame_set(f); sc.render.filepath = os.path.join(out, f"f_{f:04d}.png"); bpy.ops.render.render(write_still=True)
    else:
        if fr: sc.frame_start, sc.frame_end = (int(x) for x in fr.split("-"))
        sc.render.filepath = os.path.join(out, "f_"); bpy.ops.render.render(animation=True)
