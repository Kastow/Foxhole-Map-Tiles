#!/usr/bin/env python3
"""Compare two folders of manifests ignoring generated_at.

Exit 0 if equal, 1 if different, 2 on error.

generated_at changes on every run, so a byte comparison would make the workflow
commit forever. Every *.json in either folder is compared, so a manifest that
appears or disappears (a folder added or removed) also counts as different. A
missing or unreadable OLD file counts as different; an unreadable NEW is an error.
"""

import json
import os
import sys


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    doc.pop("generated_at", None)
    return doc


def names(folder):
    if not os.path.isdir(folder):
        return set()
    return {n for n in os.listdir(folder) if n.endswith(".json")}


def main():
    if len(sys.argv) != 3:
        print("usage: compare_info_json.py OLD_DIR NEW_DIR", file=sys.stderr)
        sys.exit(2)
    old_dir, new_dir = sys.argv[1], sys.argv[2]

    changed = []
    for name in sorted(names(old_dir) | names(new_dir)):
        new = load(os.path.join(new_dir, name))
        if new is None and name in names(new_dir):
            print(f"cannot read {os.path.join(new_dir, name)}", file=sys.stderr)
            sys.exit(2)
        if load(os.path.join(old_dir, name)) != new:
            changed.append(name)

    for name in changed:
        print(f"different: {name}")
    if not changed:
        print("same")
    sys.exit(1 if changed else 0)


if __name__ == "__main__":
    main()
