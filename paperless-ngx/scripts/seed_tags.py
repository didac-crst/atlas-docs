#!/usr/bin/env python3
"""Seed Paperless operational tags from the Git taxonomy spec.

Source of truth:
  config/paperless/tags.yaml  (mounted at /usr/src/paperless/seeds/tags.yaml)

Idempotent: creates missing tags, updates color / is_inbox_tag / parent.
Does not delete tags absent from the seed.

Run:
  docker compose exec webserver python3 /usr/src/paperless/scripts/seed_tags.py
  docker compose exec webserver python3 /usr/src/paperless/scripts/seed_tags.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


DEFAULT_SEED = Path("/usr/src/paperless/seeds/tags.yaml")


def log(msg: str) -> None:
    print(f"[seed_tags] {msg}", flush=True)


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        # Minimal fallback: Paperless image may not ship PyYAML.
        raise SystemExit(
            "PyYAML is required inside the container. "
            "If missing, run via host python with requests against the API, "
            "or install pyyaml in a one-off exec."
        ) from None

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "roots" not in data:
        raise SystemExit(f"invalid seed file: {path}")
    return data


def flatten(spec: dict) -> list[dict]:
    """Return ordered tag records with full path names."""
    colors = spec.get("colors") or {}
    rows: list[dict] = []
    for root in spec["roots"]:
        root_name = root["name"]
        root_path = root_name
        rows.append(
            {
                "path": root_path,
                "name": root_path,
                "parent_path": None,
                "color": root.get("color") or colors.get(root_name, "#a6cee3"),
                "is_inbox_tag": bool(root.get("is_inbox_tag", False)),
                "description": root.get("description") or "",
            }
        )
        for child in root.get("children") or []:
            child_name = child["name"]
            path = f"{root_name}/{child_name}"
            rows.append(
                {
                    "path": path,
                    "name": path,
                    "parent_path": root_path,
                    "color": child.get("color") or colors.get(root_name, "#a6cee3"),
                    "is_inbox_tag": bool(child.get("is_inbox_tag", False)),
                    "description": child.get("description") or "",
                }
            )
    return rows


def seed_django(rows: list[dict], *, dry_run: bool) -> int:
    src = Path("/usr/src/paperless/src")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    os.chdir(src)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
    import django

    django.setup()
    from documents.models import Tag

    by_path: dict[str, object] = {}
    created = updated = unchanged = 0

    # Index existing by name (ownerless global tags).
    existing = {t.name: t for t in Tag.objects.filter(owner__isnull=True)}

    for row in rows:
        name = row["name"]
        parent_path = row["parent_path"]
        parent = by_path.get(parent_path) if parent_path else None
        if parent_path and parent is None and parent_path in existing:
            parent = existing[parent_path]

        tag = existing.get(name)
        if tag is None:
            log(f"CREATE {name}")
            created += 1
            if not dry_run:
                tag = Tag(
                    name=name,
                    color=row["color"],
                    is_inbox_tag=row["is_inbox_tag"],
                    match="",
                    matching_algorithm=Tag.MATCH_NONE,
                )
                tag.save()
                if parent is not None:
                    tag.set_parent(parent)
                    tag.save()
                existing[name] = tag
        else:
            dirty = False
            if tag.color != row["color"]:
                log(f"UPDATE color {name}: {tag.color} -> {row['color']}")
                tag.color = row["color"]
                dirty = True
            if bool(tag.is_inbox_tag) != row["is_inbox_tag"]:
                log(
                    f"UPDATE inbox {name}: {tag.is_inbox_tag} -> {row['is_inbox_tag']}"
                )
                tag.is_inbox_tag = row["is_inbox_tag"]
                dirty = True
            current_parent = tag.get_parent()
            # Compare by path/name so --dry-run works when parents are placeholders.
            current_parent_path = current_parent.name if current_parent else None
            if parent_path != current_parent_path:
                log(f"UPDATE parent {name}: {current_parent_path} -> {parent_path}")
                dirty = True
                if not dry_run:
                    tag.set_parent(parent)
            if dirty:
                updated += 1
                if not dry_run:
                    tag.save()
            else:
                unchanged += 1

        # Prefer real Tag objects; only use a placeholder for planned creates.
        by_path[row["path"]] = existing.get(name) or (object() if dry_run else None)

    log(
        f"done created={created} updated={updated} unchanged={unchanged} dry_run={dry_run}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path(os.environ.get("PAPERLESS_TAG_SEED", str(DEFAULT_SEED))),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.seed.is_file():
        log(f"seed file not found: {args.seed}")
        return 1

    spec = load_yaml(args.seed)
    rows = flatten(spec)
    log(f"loaded {len(rows)} tags from {args.seed}")
    return seed_django(rows, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
