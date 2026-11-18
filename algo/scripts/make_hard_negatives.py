"""Export ADL sequences reviewed and labelled in confusable.yaml."""

import argparse
from pathlib import Path

import yaml

from ur_manifest import ALGO, LABELS, read_manifest, write_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ALGO / "configs/confusable.yaml")
    parser.add_argument("--output", type=Path, default=LABELS / "hard_negative.csv")
    args = parser.parse_args()
    try:
        rows = read_manifest()
        config = yaml.safe_load(args.config.read_text(encoding="utf-8-sig"))
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise ValueError("Expected a YAML mapping of sequence IDs to action types.")
        selected = []
        for seq_id, action in config.items():
            if seq_id not in rows or rows[seq_id]["label"] != "adl":
                raise ValueError(f"Expected an indexed ADL sequence, got {seq_id!r}")
            if action not in ("sit", "lie", "bend", "squat"):
                raise ValueError(f"{seq_id}: expected sit, lie, bend or squat, got {action!r}")
            selected.append(dict(rows[seq_id], confusable_type=action))
        write_csv(args.output, sorted(selected, key=lambda r: r["seq_id"]))
        print(f"{len(selected)} reviewed hard negatives -> {args.output}")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
