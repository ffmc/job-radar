"""Loads the manually-curated tool-vendor customer list from sources/target-companies.md.

Unlike remoteintech.company, this source has no per-company careers URL - only names
scraped off vendor case-study pages. `careers_url` is a bare domain guess (name with
punctuation stripped); resolve() falls back to slug-probing greenhouse/ashby/lever when
a guess is wrong, same as it does for any company whose stated URL doesn't pan out.
"""
import re
from pathlib import Path

SOURCE_PATH = Path(__file__).resolve().parent.parent / "sources" / "target-companies.md"
REGION = "tool-vendor"

LIST_RE = re.compile(r"(?:Well-known / notable|Full sample)[^:\n]*:\s*(.+?)(?=\n\s*\n|\Z)", re.S)


def _clean(raw):
    name = re.sub(r"\s*\(.*?\)", "", raw)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return name


def _slug(name):
    return "tv-" + re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def _domain_guess(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load(path=SOURCE_PATH):
    text = path.read_text()
    seen, out = set(), []
    for chunk in LIST_RE.findall(text):
        for raw in chunk.split(","):
            name = _clean(raw)
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "slug": _slug(name),
                    "name": name,
                    "region": REGION,
                    "careers_url": f"https://{_domain_guess(name)}.com",
                }
            )
    if not out:
        raise RuntimeError("target-companies.md parsed to zero rows - check its format")
    return out
