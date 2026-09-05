"""Run the crawl without a database connection, emitting JSON for external loading."""

import json
from concurrent.futures import ThreadPoolExecutor

from .boards import fetch_jobs
from .companies import scrape
from .filters import TitleFilter, load_config
from .resolve import resolve


def resolve_all(path, limit=None, workers=12):
    config = load_config()
    companies = scrape(config["regions"])
    if limit:
        companies = companies[:limit]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        pairs = list(ex.map(resolve, companies))
    for company, (ats, token) in zip(companies, pairs):
        company["ats"], company["token"] = ats, token
    with open(path, "w") as f:
        json.dump(companies, f, indent=1)
    print(f"{sum(1 for c in companies if c['ats'])}/{len(companies)} resolved -> {path}")
    return companies


def crawl_all(companies_path, path, workers=16):
    title_filter = TitleFilter(load_config())
    with open(companies_path) as f:
        companies = [c for c in json.load(f) if c.get("ats") and c.get("token")]

    def pull(c):
        try:
            return c, fetch_jobs(c["ats"], c["token"]), None
        except Exception as e:
            return c, [], f"{type(e).__name__}: {e}"[:200]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(pull, companies))

    out, errors = [], {}
    for company, jobs, error in results:
        if error:
            errors[company["slug"]] = error
            continue
        for job in jobs:
            if title_filter.matches(job["title"]):
                out.append(dict(job, slug=company["slug"], posted_at=str(job["posted_at"] or "") or None))
    with open(path, "w") as f:
        json.dump({"postings": out, "errors": errors}, f, indent=1)
    print(f"{len(out)} matching postings from {len(companies) - len(errors)} boards, "
          f"{len(errors)} errors -> {path}")
    return out, errors
