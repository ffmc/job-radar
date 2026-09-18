import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from . import db, himalayas
from .boards import fetch_jobs
from .companies import all_companies
from .filters import AgeFilter, LocationFilter, TitleFilter, load_config
from .resolve import resolve


def cmd_init(args):
    with db.connect() as conn:
        db.apply_schema(conn)
        rows = all_companies(load_config()["regions"])
        db.upsert_companies(conn, rows)
        print(f"schema applied, {len(rows)} companies upserted")


def cmd_resolve(args):
    if args.dry_run:
        companies = [
            dict(c, id=None) for c in all_companies(load_config()["regions"])[: args.limit or 20]
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
        hits = 0
        with ThreadPoolExecutor(max_workers=12) as ex:
            futures = {ex.submit(resolve, c): c for c in companies}
            for future in as_completed(futures):
                company = futures[future]
                ats, token = future.result()
                db.save_resolution(conn, company["id"], ats, token)
                hits += bool(ats)
        print(f"resolved {hits} of {len(companies)}")


def cmd_crawl(args):
    config = load_config()
    title_filter = TitleFilter(config)
    location_filter = LocationFilter(config)
    age_filter = AgeFilter(config)

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
            kept = [
                j for j in jobs
                if title_filter.matches(j["title"])
                and location_filter.matches(j["location"])
                and age_filter.matches(j["posted_at"])
            ]
            seen += len(kept)
            new += db.upsert_postings(conn, company["id"], kept)

        try:
            by_company = {}
            for j in himalayas.fetch():
                if (
                    title_filter.matches(j["title"])
                    and location_filter.matches(j["location"])
                    and age_filter.matches(j["posted_at"])
                ):
                    by_company.setdefault(j["company_slug"], []).append(j)
            for slug, jobs in by_company.items():
                company_id = db.upsert_company(conn, f"himalayas:{slug}", jobs[0]["company_name"], "himalayas")
                ok_ids.append(company_id)
                seen += len(jobs)
                new += db.upsert_postings(conn, company_id, jobs)
        except Exception as e:
            errors["himalayas"] = f"{type(e).__name__}: {e}"[:200]

        closed = db.close_stale(conn, ok_ids, run_started)
        purged = db.purge_stale(
            conn, config["freshness"]["max_age_days"], config["freshness"]["keep_undated"]
        )
        average = db.recent_average_seen(conn)
        db.finish_run(conn, run_id, len(ok_ids), seen, new, errors)

        print(
            f"run {run_id}: {len(ok_ids) - len(by_company)}/{len(companies)} boards ok "
            f"plus {len(by_company)} himalayas companies, "
            f"{seen} matching postings, {new} new, {closed} closed, "
            f"{purged} aged out, {len(errors)} errors"
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
    parser.add_argument("--report", metavar="PATH", nargs="?", const="postings.html",
                        help="write open postings to a static HTML file (default postings.html)")
    args = parser.parse_args()

    if args.report:
        from .report import main as report_main
        report_main(args.report)
    elif args.offline_resolve:
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
