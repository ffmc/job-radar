from datetime import date, datetime, timedelta, timezone

from .net import fetch_json

API = "https://himalayas.app/jobs/api"


def _day(pub_date):
    return datetime.fromtimestamp(pub_date, tz=timezone.utc).date() if pub_date else None


def fetch(since_days=3):
    """Newest-first feed, paged by cursor. Stops once a job predates the
    cutoff rather than paging through all ~100k historical jobs."""
    cutoff = date.today() - timedelta(days=since_days)
    out, cursor = [], None
    while True:
        url = f"{API}?limit=20" + (f"&cursor={cursor}" if cursor else "")
        d = fetch_json(url)
        page = d.get("jobs", [])
        if not page:
            return out
        for j in page:
            posted_at = _day(j.get("pubDate"))
            if posted_at and posted_at < cutoff:
                return out
            out.append(
                {
                    "company_slug": j.get("companySlug") or j.get("companyName", ""),
                    "company_name": j.get("companyName", ""),
                    "ats_job_id": j.get("guid", ""),
                    "title": j.get("title", ""),
                    "location": ", ".join(j.get("locationRestrictions") or []),
                    "url": j.get("applicationLink", ""),
                    "posted_at": posted_at,
                }
            )
        cursor = d.get("nextCursor")
        if not cursor:
            return out
