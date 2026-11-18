"""Stratify whole sequences and publish the three membership lists together."""

import argparse
import random
from pathlib import Path
from uuid import uuid4

from ur_manifest import ALGO, read_manifest, write_csv


SIZES = {"fall": (18, 6, 6), "adl": (24, 8, 8)}
SEED = 42


def split(rows):
    rng = random.Random(SEED)
    groups = {"train": [], "val": [], "test": []}
    for label, sizes in SIZES.items():
        ids = sorted(seq_id for seq_id, row in rows.items() if row["label"] == label)
        if len(ids) != sum(sizes):
            raise ValueError(f"Expected {sum(sizes)} {label} sequences, found {len(ids)}")
        rng.shuffle(ids)
        start = 0
        for name, count in zip(groups, sizes):
            groups[name].extend(rows[seq_id] for seq_id in ids[start:start + count])
            start += count
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ALGO / "data/splits")
    args = parser.parse_args()
    target = args.output_dir.resolve()
    try:
        if (target / "test.csv").exists():
            raise ValueError(f"Frozen test manifest exists. Refusing to overwrite: {target / 'test.csv'}")
        groups = split(read_manifest())
        target.parent.mkdir(parents=True, exist_ok=True)
        ready = target.with_name(f".{target.name}-{uuid4().hex}")
        ready.mkdir()
        try:
            for name, members in groups.items():
                write_csv(ready / f"{name}.csv", members, ("seq_id", "label"))
            # Rename on the same filesystem publishes all three files atomically.
            # A concurrent winner leaves a non-empty directory, which rename cannot replace.
            ready.rename(target)
        finally:
            if ready.exists():
                for name in groups:
                    (ready / f"{name}.csv").unlink(missing_ok=True)
                ready.rmdir()
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    for name, members in groups.items():
        falls = sum(row["label"] == "fall" for row in members)
        print(f"{name}: {falls} fall + {len(members) - falls} adl -> {target / (name + '.csv')}")


if __name__ == "__main__":
    main()
