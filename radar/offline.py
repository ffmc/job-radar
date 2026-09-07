"""Run the crawl without a database connection, emitting JSON for external loading."""

import json
import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor

from .boards import fetch_jobs
from .companies import scrape
from .filters import AgeFilter, LocationFilter, TitleFilter, load_config
from .resolve import resolve

# A hung DNS lookup cannot be interrupted in a thread, so resolution runs in
# processes that can be killed when they overrun.
PER_COMPANY_TIMEOUT = 90


def resolve_all(path, limit=None, workers=12):
    config = load_config()
    companies = scrape(config["regions"])
    if limit:
        companies = companies[:limit]
    started = time.time()
    pool = multiprocessing.Pool(processes=workers)
    pending = [(c, pool.apply_async(resolve, (c,))) for c in companies]
    for done, (company, result) in enumerate(pending, start=1):
        try:
            company["ats"], company["token"] = result.get(timeout=PER_COMPANY_TIMEOUT)
        except Exception:
            company["ats"], company["token"] = None, None
        if done % 25 == 0 or done == len(companies):
            hits = sum(1 for c in companies if c.get("ats"))
            print(
                f"  {done}/{len(companies)} companies, {hits} resolved, "
                f"{time.time() - started:.0f}s",
                flush=True,
            )
    pool.terminate()
    pool.join()
    with open(path, "w") as f:
        json.dump(companies, f, indent=1)
    print(f"{sum(1 for c in companies if c['ats'])}/{len(companies)} resolved -> {path}")
    return companies


def crawl_all(companies_path, path, workers=16):
    config = load_config()
    title_filter = TitleFilter(config)
    location_filter = LocationFilter(config)
    age_filter = AgeFilter(config)
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
            if (title_filter.matches(job["title"])
                    and location_filter.matches(job["location"])
                    and age_filter.matches(job["posted_at"])):
                out.append(dict(job, slug=company["slug"], posted_at=str(job["posted_at"] or "") or None))
    with open(path, "w") as f:
        json.dump({"postings": out, "errors": errors}, f, indent=1)
    print(f"{len(out)} matching postings from {len(companies) - len(errors)} boards, "
          f"{len(errors)} errors -> {path}")
    return out, errors
