#!/usr/bin/env python3
"""Generate the info.json manifest plus one per-file manifest per top-level folder.

Root files and anything starting with "." are skipped. Every folder gets a hash
built from its children's hashes, so a hash change points straight at what moved.

info.json holds the folder tree only (hash, size, item_count). Each top-level
folder entry names its own detail file, e.g. "Sat Tiles" -> info.sat.tiles.json,
which holds that folder's full tree including every file. A client only has to
fetch the detail files of the folders whose hash changed.

All manifests are written into one folder (.info by default), so detail_file
names are relative to info.json. That folder starts with "." and is therefore
skipped by the scan.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

MANIFEST_VERSION = 1
CHUNK = 1 << 20


def file_node(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
            size += len(chunk)
    return {"hash": h.hexdigest(), "size": size}


def folder_node(path, skip_files=False):
    """Walk one folder. Children are sorted by name so output is deterministic."""
    folders, files = {}, {}
    for entry in sorted(os.scandir(path), key=lambda e: e.name):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            folders[entry.name] = folder_node(entry.path)
        elif entry.is_file() and not skip_files:
            files[entry.name] = file_node(entry.path)

    children = [("d", n, v) for n, v in folders.items()]
    children += [("f", n, v) for n, v in files.items()]
    h = hashlib.sha256()
    for kind, name, node in sorted(children, key=lambda c: c[1]):
        h.update(f"{kind} {node['hash']} {name}\n".encode())

    return {
        "hash": h.hexdigest(),
        "size": sum(n["size"] for n in (*folders.values(), *files.values())),
        "item_count": sum(n["item_count"] for n in folders.values()) + len(files),
        "folders": folders,
        "files": files,
    }


def without_files(folders):
    return {
        name: {
            "hash": n["hash"],
            "size": n["size"],
            "item_count": n["item_count"],
            "folders": without_files(n["folders"]),
        }
        for name, n in folders.items()
    }


def detail_name(prefix, folder):
    """ "Fly Height Tiles" -> "info.fly.height.tiles.json"."""
    words = re.findall(r"[a-z0-9]+", folder.lower())
    if not words:
        sys.exit(f"cannot build a manifest name for folder {folder!r}")
    return f"{prefix}.{'.'.join(words)}.json"


def header(generated_at):
    return {
        "manifest_version": MANIFEST_VERSION,
        "generated_at": generated_at,
        "hash_algorithm": "sha256",
    }


def info_document(root, generated_at, names):
    doc = header(generated_at)
    doc["hash"] = root["hash"]
    doc["size"] = root["size"]
    doc["item_count"] = root["item_count"]
    doc["folders"] = {
        name: {
            "hash": n["hash"],
            "size": n["size"],
            "item_count": n["item_count"],
            "detail_file": names[name],
            "folders": without_files(n["folders"]),
        }
        for name, n in root["folders"].items()
    }
    return doc


def detail_document(name, node, generated_at):
    doc = header(generated_at)
    doc["folder"] = name
    doc["hash"] = node["hash"]
    doc["size"] = node["size"]
    doc["item_count"] = node["item_count"]
    doc["folders"] = node["folders"]
    doc["files"] = node["files"]
    return doc


def write_json(path, doc, indent):
    separators = (",", ": ") if indent else (",", ":")
    text = json.dumps(doc, indent=indent, separators=separators, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=".", help="repository root to scan")
    p.add_argument("--out-dir", default=".info", help="where to write the manifests")
    p.add_argument(
        "--prefix",
        default="info",
        help="manifest name prefix: PREFIX.json and PREFIX.<folder>.json",
    )
    args = p.parse_args()

    root = folder_node(args.root, skip_files=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    names = {name: detail_name(args.prefix, name) for name in root["folders"]}
    clashes = {n for n in names.values() if list(names.values()).count(n) > 1}
    if clashes:
        sys.exit(f"folders map to the same manifest name: {sorted(clashes)}")

    os.makedirs(args.out_dir, exist_ok=True)
    write_json(
        os.path.join(args.out_dir, f"{args.prefix}.json"),
        info_document(root, generated_at, names),
        indent=2,
    )
    for name, node in root["folders"].items():
        write_json(
            os.path.join(args.out_dir, names[name]),
            detail_document(name, node, generated_at),
            indent=None,
        )
    print(f"{root['item_count']} files, {root['size']} bytes, hash {root['hash']}")


if __name__ == "__main__":
    main()
