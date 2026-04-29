import json
from pathlib import Path
from collections import defaultdict

paths = {
    "train": Path("tenacious_bench_v0.1/train/tasks.jsonl"),
    "dev": Path("tenacious_bench_v0.1/dev/tasks.jsonl"),
    "held_out": Path("tenacious_bench_v0.1/held_out/tasks.jsonl"),
}

cell = defaultdict(int)  # (dim, partition, mode) -> count
dim_tot = defaultdict(int)
part_tot = defaultdict(int)
mode_tot = defaultdict(int)
grand = 0

for partition, p in paths.items():
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        mode = t.get("source_mode", "?")
        seg = t.get("input", {}).get("hiring_signal_brief", {}).get(
            "primary_segment_match", ""
        )
        dim = SEGMENT_TO_DIM.get(seg, f"other:{seg or 'none'}")
        cell[(dim, partition, mode)] += 1
        dim_tot[dim] += 1
        part_tot[partition] += 1
        mode_tot[mode] += 1
        grand += 1

print("grand_total", grand)
print("partition_totals", dict(part_tot))
print("mode_totals", dict(mode_tot))
print("dim_totals", dict(dim_tot))
print("--- crosstab keys ---")
for k in sorted(cell.keys()):
    print(k, cell[k])
