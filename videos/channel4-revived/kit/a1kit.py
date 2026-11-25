"""A1 realistic kit for every Channel 4 Short (look picked 23 Nov 2026: "A1 Realistic").
Geometry helpers come from style-test/common.py. This file adds the A1 materials (CC0 Poly Haven textures plus
procedural steel, gravel, concrete, grass, asphalt, x-ray glass and glow), the photo sky, cameras, the Cycles setup and rendering.
Use:  import sys; sys.path.insert(0, ".../kit"); from a1kit import *"""
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
KIT = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(KIT)
sys.path.insert(0, os.path.join(ROOT, "style-test"))
from common import key, link, mesh_obj, bm_obj, bsdf_of, superellipse, BOX_F   # noqa: E402  (shared geometry helpers)
PH = os.path.join(ROOT, "style-test", "assets", "polyhaven")
HDRI = os.path.join(PH, "kloofendal_48d_partly_cloudy_puresky", "kloofendal_48d_partly_cloudy_puresky_4k.hdr")

def scene(n_frames, fps=24):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = fps; sc.frame_start, sc.frame_end = 1, n_frames
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    sc.render.resolution_percentage = int(os.environ.get("PCT", "67"))
    return sc

def box(name, c, s, m, loc=(0, 0, 0), bevel=0.0, parent=None):
    cx, cy, cz = c; sx, sy, sz = (a / 2 for a in s)
    ob = mesh_obj(name, [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)], BOX_F, [m], loc=loc)
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL"); md.width = bevel; md.segments = 3; md.harden_normals = True; ob.data.shade_smooth()
    if parent: ob.parent = parent
    return ob

# ---------- materials ----------
def _new(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; return m, m.node_tree, bsdf_of(m)

def plain(name, rgb, rough=0.5, metal=0.0, coat=0.0, emit=None, estr=0.0):
    m, nt, b = _new(name)
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal; b.inputs["Coat Weight"].default_value = coat
    if emit: b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = estr
    m.diffuse_color = (*rgb, 1); return m

def img(asset, kind, non_color=False):
    d = os.path.join(PH, asset); f = next(x for x in sorted(os.listdir(d)) if f"_{kind}_" in x)
    im = bpy.data.images.load(os.path.join(d, f), check_existing=True)
    if non_color: im.colorspace_settings.name = "Non-Color"
    return im

def _stats(im):
    a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32); im.pixels.foreach_get(a)
    lum = (a[0::4] * 0.3 + a[1::4] * 0.59 + a[2::4] * 0.11)[::7]; return float(lum.mean()), float(lum.std())

def pbr(name, asset, scale, color, rough=(0.2, 0.5), nor=0.5, metal=0.0, coat=0.0, var=(0.85, 1.06)):
    """Colour = paint colour x the photo texture's own light/dark variation (its detail without its hue), plus its normal and roughness maps."""
    m, nt, b = _new(name); L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (scale,) * 3
    L(tc.outputs["Object"], mp.inputs["Vector"])
    def t(kind, nc):
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = img(asset, kind, nc); n.projection = "BOX"; n.projection_blend = 0.3
        L(mp.outputs[0], n.inputs["Vector"]); return n
    d, r, nm = t("diff", False), t("rough", True), t("nor_gl", True)
    dm, ds = _stats(d.image); rm, rs = _stats(r.image)
    bw = nt.nodes.new("ShaderNodeRGBToBW"); L(d.outputs["Color"], bw.inputs[0])
    v = nt.nodes.new("ShaderNodeMapRange"); v.inputs["From Min"].default_value = dm - 2 * ds; v.inputs["From Max"].default_value = dm + 2 * ds
    v.inputs["To Min"].default_value, v.inputs["To Max"].default_value = var; L(bw.outputs[0], v.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
    mul.inputs[6].default_value = (*color, 1)
    vc = nt.nodes.new("ShaderNodeCombineColor"); [L(v.outputs[0], vc.inputs[i]) for i in range(3)]; L(vc.outputs[0], mul.inputs[7])
    L(mul.outputs[2], b.inputs["Base Color"])
    rr = nt.nodes.new("ShaderNodeMapRange"); rr.inputs["From Min"].default_value = rm - 2 * rs; rr.inputs["From Max"].default_value = rm + 2 * rs
    rr.inputs["To Min"].default_value, rr.inputs["To Max"].default_value = rough; L(r.outputs["Color"], rr.inputs["Value"]); L(rr.outputs[0], b.inputs["Roughness"])
    nn = nt.nodes.new("ShaderNodeNormalMap"); nn.inputs["Strength"].default_value = nor; L(nm.outputs["Color"], nn.inputs["Color"]); L(nn.outputs[0], b.inputs["Normal"])
    b.inputs["Metallic"].default_value = metal; b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*color, 1); return m

def _noise_mix(name, c1, c2, scale, rough, bump, detail=6.0, voronoi=False, metal=0.0):
    """Procedural surface: two colours mixed by noise (or Voronoi cells for stones), with bump."""
    m, nt, b = _new(name); L = nt.links.new
    tc = nt.nodes.new("ShaderNodeTexCoord")
    if voronoi:
        tx = nt.nodes.new("ShaderNodeTexVoronoi"); tx.inputs["Scale"].default_value = scale; fac = tx.outputs["Distance"]; colsrc = tx.outputs["Color"]
    else:
        tx = nt.nodes.new("ShaderNodeTexNoise"); tx.inputs["Scale"].default_value = scale; tx.inputs["Detail"].default_value = detail; fac = tx.outputs["Fac"]; colsrc = None
    L(tc.outputs["Object"], tx.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); el = ramp.color_ramp.elements; el[0].color = (*c1, 1); el[1].color = (*c2, 1)
    if voronoi:
        bwn = nt.nodes.new("ShaderNodeRGBToBW"); L(colsrc, bwn.inputs[0]); L(bwn.outputs[0], ramp.inputs[0])
    else: L(fac, ramp.inputs[0])
    L(ramp.outputs[0], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump; L(fac, bp.inputs["Height"]); L(bp.outputs[0], b.inputs["Normal"])
    m.diffuse_color = (*c1, 1); return m

def gravel(name="ballast"): return _noise_mix(name, (0.12, 0.11, 0.1), (0.42, 0.4, 0.37), 28.0, 0.85, 0.6, voronoi=True)
def concrete(name="concrete"): return _noise_mix(name, (0.38, 0.37, 0.35), (0.55, 0.54, 0.51), 9.0, 0.8, 0.08)
def asphalt(name="asphalt"): return _noise_mix(name, (0.025, 0.025, 0.028), (0.07, 0.07, 0.075), 60.0, 0.85, 0.15)
def grass(name="grass"): return _noise_mix(name, (0.03, 0.09, 0.015), (0.1, 0.2, 0.03), 0.6, 0.9, 0.3, detail=10.0)
def steel(name="steel", rgb=(0.56, 0.57, 0.58), rough=0.32): return plain(name, rgb, rough, metal=1.0)
def rust(name="rail_rust"): return _noise_mix(name, (0.12, 0.05, 0.025), (0.26, 0.12, 0.05), 14.0, 0.75, 0.3)

def glow(name, rgb, strength=4.0, alpha=0.85):
    """Pure light (callouts, load lines). Doesn't light or tint the scene when the object's ray visibility is limited with no_light()."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs[0].default_value = alpha
    o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(e.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], o.inputs[0])
    return m

def no_light(ob):
    ob.visible_diffuse = ob.visible_glossy = ob.visible_shadow = ob.visible_transmission = False; return ob

def xray(name="xray", rgb=(0.92, 0.96, 1.0), edge=(0.3, 0.75, 1.0)):
    """See-through engineering shell: faint body with glowing edges (Fresnel)."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); L = nt.links.new
    lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.12
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.inputs[0].default_value = (*rgb, 1)
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*edge, 1); e.inputs[1].default_value = 2.5
    mx = nt.nodes.new("ShaderNodeMixShader"); L(lw.outputs["Facing"], mx.inputs[0]); L(tr.outputs[0], mx.inputs[1]); L(e.outputs[0], mx.inputs[2])
    L(mx.outputs[0], nt.nodes.new("ShaderNodeOutputMaterial").inputs[0]); return m

# ---------- world ----------
def photo_sky(strength=1.0, sun_az_deg=-57.3):
    """Poly Haven kloofendal puresky HDRI; its sun (azimuth 145.8 deg as measured) is turned to sun_az_deg."""
    sc = bpy.context.scene; w = bpy.data.worlds.new("sky"); sc.world = w; w.use_nodes = True; wn = w.node_tree
    bg = next(n for n in wn.nodes if n.type == "BACKGROUND"); env = wn.nodes.new("ShaderNodeTexEnvironment"); env.image = bpy.data.images.load(HDRI, check_existing=True)
    tcw = wn.nodes.new("ShaderNodeTexCoord"); mpw = wn.nodes.new("ShaderNodeMapping")
    mpw.inputs["Rotation"].default_value = (0, 0, math.radians(145.8) - math.radians(sun_az_deg))
    wn.links.new(tcw.outputs["Generated"], mpw.inputs["Vector"]); wn.links.new(mpw.outputs[0], env.inputs["Vector"]); wn.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength; return w

# ---------- cameras ----------
def camera(name, lens, focus=None, fstop=2.8):
    c = link(bpy.data.objects.new(name, bpy.data.cameras.new(name))); c.data.lens = lens; c.data.clip_end = 5000; c.data.clip_start = 0.02
    if focus is not None:
        fo = focus if isinstance(focus, bpy.types.Object) else link(bpy.data.objects.new(name + "_focus", None))
        if not isinstance(focus, bpy.types.Object): fo.location = focus
        c.data.dof.use_dof = True; c.data.dof.focus_object = fo; c.data.dof.aperture_fstop = fstop
    return c

def fill_light(cam, energy=150.0, size=3.0):
    """Soft light riding on a camera (lifts shadows under trains and inside cutaways)."""
    lt = link(bpy.data.objects.new(cam.name + "_fill", bpy.data.lights.new(cam.name + "_fill", "AREA"))); lt.data.energy = energy; lt.data.size = size
    lt.parent = cam; lt.location = (0, 0.4, 0); return lt

def aim(c, frame, loc, tgt, interp="BEZIER"):
    loc = Vector(loc); key(c, "location", frame, loc, interp); key(c, "rotation_euler", frame, (Vector(tgt) - loc).to_track_quat("-Z", "Y").to_euler(), interp)

# ---------- render ----------
def cycles(spp=None):
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "GPU"; sc.cycles.samples = int(os.environ.get("SPP", spp or 32))
    sc.cycles.use_denoising = True; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02; sc.cycles.max_bounces = 6
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences; pr.compute_device_type = "METAL"; pr.get_devices()
        for d in pr.devices: d.use = True
    except Exception as ex: print("METAL", ex)
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Punchy"; sc.view_settings.exposure = float(os.environ.get("EXPO", "0.0"))
    sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.4

def render(out_dir, blend_path=None):
    sc = bpy.context.scene; out = os.environ.get("OUT") or out_dir; os.makedirs(out, exist_ok=True)
    if blend_path: bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    fr = os.environ.get("FRAMES", "")
    if fr and "-" not in fr:
        for f in [int(x) for x in fr.split(",")]:
            sc.frame_set(f); sc.render.filepath = os.path.join(out, f"f_{f:04d}.png"); bpy.ops.render.render(write_still=True)
    else:
        if fr: sc.frame_start, sc.frame_end = (int(x) for x in fr.split("-"))
        sc.render.filepath = os.path.join(out, "f_"); bpy.ops.render.render(animation=True)
