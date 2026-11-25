"""Read ci/render-request.txt and print the job plan for the workflow."""
import json, os
req = {}
for line in open(os.path.join(os.path.dirname(__file__), "render-request.txt")):
    line = line.split("#")[0].strip()
    if "=" in line:
        k, v = line.split("=", 1); req[k.strip()] = v.strip()
first, last = int(req.get("FIRST", 1)), int(req.get("LAST", 24))
per = max(1, int(req.get("FRAMES_PER_JOB", 2)))
chunks = [f"{a}-{min(a + per - 1, last)}" for a in range(first, last + 1, per)]
assert len(chunks) <= 256, "too many jobs: raise FRAMES_PER_JOB"
print("chunks=" + json.dumps(chunks))
for k, d in (("SHORT", "s01-train-wheels"), ("PCT", "67"), ("SPP", "32"), ("NAME", "render")):
    print(f"{k.lower()}={req.get(k, d)}")
print(f"first={first}")
