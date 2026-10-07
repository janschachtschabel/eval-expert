"""Compare the audited metric implementation with the remediated one, same data/process."""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.benchmarks import compare_fields

legacy = {"__name__": "app.audited_benchmarks", "__package__": "app"}
source = subprocess.check_output(
    [
        "git",
        "show",
        "ea703bcd76c9d823d436c0b9825e2dab461e4c7b:backend/app/benchmarks.py",
    ],
    cwd=ROOT,
    text=True,
)
# This opt-in benchmark executes only the trusted, pinned repository baseline.
exec(compile(source, "audited_benchmarks.py", "exec"), legacy)  # noqa: S102
specs = [
    {
        "name": "subject",
        "output_path": "/subject",
        "reference_path": "/subject",
        "aliases": {},
    }
]
results = [
    {
        "status": "success",
        "reference": {"subject": [str(i)]},
        "output": {"subject": [str(i)]},
    }
    for i in range(1000)
]
timings = {}
summaries = []
for name, operation in [
    ("audited", legacy["compare_fields"]),
    ("remediated", compare_fields),
]:
    start = time.perf_counter()
    summaries.append(operation(results, specs))
    timings[name] = time.perf_counter() - start
assert summaries[0] == summaries[1]
timings["ratio"] = timings["audited"] / timings["remediated"]
timings["cases"] = timings["labels"] = 1000
timings["identical_metrics"] = True
print(json.dumps(timings, indent=2))
