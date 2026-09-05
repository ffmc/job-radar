import re
from datetime import date, datetime

from .net import fetch, fetch_json, post_json


def _day(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value / 1000 if value > 1e11 else value).date()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    return date(*map(int, m.groups())) if m else None


def greenhouse(token):
    d = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    return [
        {
            "ats_job_id": str(j["id"]),
            "title": j["title"],
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "posted_at": _day(j.get("updated_at")),
        }
        for j in d.get("jobs", [])
    ]


def lever(token):
    for host in ("api.lever.co", "api.eu.lever.co"):
        try:
            d = fetch_json(f"https://{host}/v0/postings/{token}?mode=json")
        except Exception:
            continue
        if d:
            return [
                {
                    "ats_job_id": j["id"],
                    "title": j["text"],
                    "location": (j.get("categories") or {}).get("location", ""),
                    "url": j.get("hostedUrl", ""),
                    "posted_at": _day(j.get("createdAt")),
                }
                for j in d
            ]
    return []


ASHBY_QUERY = (
    "query ApiJobBoardWithTeams($organizationHostedJobsPageName:String!)"
    "{jobBoard:jobBoardWithTeams(organizationHostedJobsPageName:$organizationHostedJobsPageName)"
    "{jobPostings{id title locationName publishedDate}}}"
)


def ashby(token):
    d = post_json(
        "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams",
        {"query": ASHBY_QUERY, "variables": {"organizationHostedJobsPageName": token}},
    )
    board = (d.get("data") or {}).get("jobBoard") or {}
    return [
        {
            "ats_job_id": j["id"],
            "title": j["title"],
            "location": j.get("locationName", ""),
            "url": f"https://jobs.ashbyhq.com/{token}/{j['id']}",
            "posted_at": _day(j.get("publishedDate")),
        }
        for j in board.get("jobPostings", [])
    ]


def workable(token):
    d = fetch_json(f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true")
    return [
        {
            "ats_job_id": str(j.get("shortcode") or j.get("id")),
            "title": j["title"],
            "location": ", ".join(
                x for x in [j.get("city") or "", j.get("country") or ""] if x
            ),
            "url": j.get("url", ""),
            "posted_at": _day(j.get("published_on") or j.get("created_at")),
        }
        for j in d.get("jobs", [])
    ]


def recruitee(token):
    d = fetch_json(f"https://{token}.recruitee.com/api/offers/")
    return [
        {
            "ats_job_id": str(j["id"]),
            "title": j["title"],
            "location": j.get("location", ""),
            "url": j.get("careers_url", ""),
            "posted_at": _day(j.get("published_at")),
        }
        for j in d.get("offers", [])
    ]


def smartrecruiters(token):
    out, offset = [], 0
    while True:
        d = fetch_json(
            f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
            f"?limit=100&offset={offset}"
        )
        page = d.get("content", [])
        out += [
            {
                "ats_job_id": j["id"],
                "title": j["name"],
                "location": (j.get("location") or {}).get("city", ""),
                "url": f"https://jobs.smartrecruiters.com/{token}/{j['id']}",
                "posted_at": _day(j.get("releasedDate")),
            }
            for j in page
        ]
        offset += 100
        if not page or offset >= d.get("totalFound", 0):
            return out


def personio(token):
    body = fetch(f"https://{token}.jobs.personio.com/xml")[1]
    positions = re.findall(r"<position>(.*?)</position>", body, re.S)
    out = []
    for p in positions:
        def tag(name):
            m = re.search(rf"<{name}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{name}>", p, re.S)
            return m.group(1).strip() if m else ""

        out.append(
            {
                "ats_job_id": tag("id"),
                "title": tag("name"),
                "location": tag("office"),
                "url": f"https://{token}.jobs.personio.com/job/{tag('id')}",
                "posted_at": _day(tag("createdAt")),
            }
        )
    return out


def breezy(token):
    d = fetch_json(f"https://{token}.breezy.hr/json")
    return [
        {
            "ats_job_id": j["id"],
            "title": j["name"],
            "location": ((j.get("location") or {}).get("name") or ""),
            "url": j.get("url", ""),
            "posted_at": _day(j.get("published_date") or j.get("creation_date")),
        }
        for j in d
    ]


def teamtailor(token):
    d = fetch_json(f"https://{token}.teamtailor.com/jobs.json")
    return [
        {
            "ats_job_id": str(j.get("id") or j.get("url")),
            "title": j.get("title", ""),
            "location": "",
            "url": j.get("url", ""),
            "posted_at": _day(j.get("date_published")),
        }
        for j in d.get("items", [])
    ]


def bamboohr(token):
    d = fetch_json(f"https://{token}.bamboohr.com/careers/list")
    out = []
    for j in d.get("result", []):
        loc = j.get("location") or {}
        out.append(
            {
                "ats_job_id": str(j["id"]),
                "title": j["jobOpeningName"],
                "location": ", ".join(
                    x for x in [loc.get("city") or "", loc.get("country") or ""] if x
                ),
                "url": f"https://{token}.bamboohr.com/careers/{j['id']}",
                "posted_at": None,
            }
        )
    return out


def rippling(token):
    d = fetch_json(f"https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs")
    return [
        {
            "ats_job_id": str(j.get("uuid") or j.get("id")),
            "title": j.get("name", ""),
            "location": (j.get("workLocation") or {}).get("label", ""),
            "url": j.get("url") or f"https://ats.rippling.com/{token}/jobs",
            "posted_at": None,
        }
        for j in d
    ]


def workday(token):
    tenant, host, site = token.split("|")
    base = f"https://{tenant}.{host}.myworkdayjobs.com"
    out, offset, total = [], 0, None
    while True:
        d = post_json(
            f"{base}/wday/cxs/{tenant}/{site}/jobs",
            {"limit": 20, "offset": offset, "searchText": "", "appliedFacets": {}},
        )
        page = d.get("jobPostings", [])
        if total is None:
            total = d.get("total") or 0
        for j in page:
            path = j.get("externalPath", "")
            out.append(
                {
                    "ats_job_id": j.get("bulletFields", [path])[0] if j.get("bulletFields") else path,
                    "title": j.get("title", ""),
                    "location": j.get("locationsText", ""),
                    "url": f"{base}/{site}{path}",
                    "posted_at": None,
                }
            )
        offset += 20
        if not page or offset >= total or offset > 2000:
            return out


HANDLERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
    "personio": personio,
    "breezy": breezy,
    "teamtailor": teamtailor,
    "bamboohr": bamboohr,
    "rippling": rippling,
    "workday": workday,
}


def fetch_jobs(ats, token):
    return HANDLERS[ats](token)
