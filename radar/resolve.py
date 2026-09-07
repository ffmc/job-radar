import difflib
import re
from urllib.parse import urljoin, urlparse

from .boards import fetch_jobs
from .net import MAX_BODY, fetch, fetch_json, post_json
from .resolve_patterns import BAD_TOKENS, PATTERNS, LINK_HINT, LINK_RE


PROBE = {"timeout": 10, "attempts": 1}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _plausible(token, company):
    if not token or token.lower() in BAD_TOKENS:
        return False
    t = _norm(token)
    for ref in (_norm(company["slug"]), _norm(company["name"])):
        if not ref:
            continue
        if t in ref or ref in t:
            return True
        if difflib.SequenceMatcher(None, t, ref).ratio() >= 0.55:
            return True
    return False


def _scan(text, company, trusted):
    text = text[:MAX_BODY]
    for ats, pattern in PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            token = "|".join(g for g in m.groups() if g) if m.groups() else None
            if not token:
                continue
            first = token.split("|")[0]
            if trusted or _plausible(first, company):
                return ats, token
    return None, None


def _validate(ats, token):
    try:
        return bool(fetch_jobs(ats, token))
    except Exception:
        return False


def _probe_slug(company):
    seen = set()
    for cand in (company["slug"], company["slug"].replace("-", ""), _norm(company["name"])):
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            if fetch_json(
                f"https://boards-api.greenhouse.io/v1/boards/{cand}/jobs", **PROBE
            ).get("jobs"):
                return "greenhouse", cand
        except Exception:
            pass
        try:
            d = post_json(
                "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams",
                {
                    "query": (
                        "query ApiJobBoardWithTeams($organizationHostedJobsPageName:String!)"
                        "{jobBoard:jobBoardWithTeams("
                        "organizationHostedJobsPageName:$organizationHostedJobsPageName)"
                        "{jobPostings{id}}}"
                    ),
                    "variables": {"organizationHostedJobsPageName": cand},
                },
                **PROBE,
            )
            board = (d.get("data") or {}).get("jobBoard") or {}
            if board.get("jobPostings"):
                return "ashby", cand
        except Exception:
            pass
        for host in ("api.lever.co", "api.eu.lever.co"):
            try:
                if fetch_json(f"https://{host}/v0/postings/{cand}?mode=json", **PROBE):
                    return "lever", cand
            except Exception:
                pass
    return None, None


def _hop_links(base_url, body, limit=4):
    out, seen = [], set()
    for href, text in LINK_RE.findall(body):
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        if not (LINK_HINT.search(href) or LINK_HINT.search(text)):
            continue
        url = urljoin(base_url, href)
        if not urlparse(url).netloc or url == base_url or url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def resolve(company):
    """Return (ats, token) or (None, None). A hit counts only if the board returns jobs."""
    try:
        final, body = fetch(company["careers_url"], timeout=25)
    except Exception:
        final, body = company["careers_url"], ""

    ats, token = _scan(final + "\n" + body, company, trusted=True)
    if ats and _validate(ats, token):
        return ats, token

    ats, token = _probe_slug(company)
    if ats:
        return ats, token

    for url in _hop_links(final, body):
        try:
            hop_final, hop_body = fetch(url, timeout=15)
        except Exception:
            continue
        ats, token = _scan(hop_final + "\n" + hop_body, company, trusted=False)
        if ats and _validate(ats, token):
            return ats, token
    return None, None
