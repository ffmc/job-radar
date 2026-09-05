import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import db
from .boards import fetch_jobs
from .companies import scrape
from .filters import TitleFilter, load_config
from .resolve import resolve


def cmd_init(args):
    with db.connect() as conn:
        db.apply_schema(conn)
        rows = scrape(load_config()["regions"])
        db.upsert_companies(conn, rows)
        print(f"schema applied, {len(rows)} companies upserted")


def cmd_resolve(args):
    if args.dry_run:
        companies = [
            dict(c, id=None) for c in scrape(load_config()["regions"])[: args.limit or 20]
        ]
        hits = 0
        for c in companies:
            ats, token = resolve(c)
            print(f"  {c['name'][:28]:28} {ats or '-':16} {token or ''}")
            hits += bool(ats)
        print(f"{hits}/{len(companies)} resolved")
        return

    with db.connect() as conn:
        companies = db.companies_to_resolve(conn, args.limit, only_unresolved=not args.all)
        print(f"resolving {len(companies)} companies")
        with ThreadPoolExecutor(max_workers=12) as ex:
            results = list(ex.map(lambda c: (c["id"], resolve(c)), companies))
        for company_id, (ats, token) in results:
            db.save_resolution(conn, company_id, ats, token)
        print(f"resolved {sum(1 for _, (a, _t) in results if a)} of {len(companies)}")


def cmd_crawl(args):
    config = load_config()
    title_filter = TitleFilter(config)

    with db.connect() as conn:
        companies = db.resolved_companies(conn)
        run_id = db.start_run(conn)
        run_started = datetime.now(timezone.utc)

        def pull(company):
            try:
                return company, fetch_jobs(company["ats"], company["token"]), None
            except Exception as e:
                return company, [], f"{type(e).__name__}: {e}"[:200]

        with ThreadPoolExecutor(max_workers=16) as ex:
            results = list(ex.map(pull, companies))

        errors, seen, new, ok_ids = {}, 0, 0, []
        for company, jobs, error in results:
            if error:
                errors[company["name"]] = error
                continue
            ok_ids.append(company["id"])
            kept = [j for j in jobs if title_filter.matches(j["title"])]
            seen += len(kept)
            new += db.upsert_postings(conn, company["id"], kept)

        closed = db.close_stale(conn, ok_ids, run_started)
        average = db.recent_average_seen(conn)
        db.finish_run(conn, run_id, len(ok_ids), seen, new, errors)

        print(
            f"run {run_id}: {len(ok_ids)}/{len(companies)} boards ok, "
            f"{seen} matching postings, {new} new, {closed} closed, {len(errors)} errors"
        )
        if average and seen < average * 0.5:
            print(
                f"FAIL: {seen} postings is under half the 7-day average of {average:.0f}",
                file=sys.stderr,
            )
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="radar")
    parser.add_argument("--init", action="store_true", help="apply schema and load company list")
    parser.add_argument("--resolve", action="store_true", help="resolve companies to job boards")
    parser.add_argument("--all", action="store_true", help="re-resolve already-resolved companies")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true", help="resolve without touching the database")
    parser.add_argument("--offline-resolve", metavar="PATH", help="resolve to a JSON file, no database")
    parser.add_argument("--offline-crawl", nargs=2, metavar=("COMPANIES", "OUT"),
                        help="crawl from a resolved JSON file into a JSON file, no database")
    args = parser.parse_args()

    if args.offline_resolve:
        from .offline import resolve_all
        resolve_all(args.offline_resolve, args.limit)
    elif args.offline_crawl:
        from .offline import crawl_all
        crawl_all(*args.offline_crawl)
    elif args.init:
        cmd_init(args)
    elif args.resolve:
        cmd_resolve(args)
    else:
        cmd_crawl(args)


if __name__ == "__main__":
    main()
