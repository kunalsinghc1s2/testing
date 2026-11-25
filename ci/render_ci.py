"""Run a Short's build.py on a machine with no graphics card (GitHub's free runners).
Leaves the kit untouched: it only switches Cycles to the CPU after the kit sets it up.
Run: blender -b --factory-startup --python ci/render_ci.py   (env: SHORT, PCT, SPP, FRAMES, OUT)"""
import os, sys, runpy
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "videos", "channel4-revived")
sys.path.insert(0, os.path.join(ROOT, "kit"))
import a1kit, bpy  # noqa: E402

_cycles = a1kit.cycles
def cycles_cpu(spp=None):
    _cycles(spp)
    sc = bpy.context.scene
    sc.cycles.device = "CPU"
    sc.render.threads_mode = "AUTO"
a1kit.cycles = cycles_cpu

short = os.environ.get("SHORT", "s01-train-wheels")
runpy.run_path(os.path.join(ROOT, "shorts", short, "build.py"), run_name="__main__")
