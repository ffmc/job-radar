import re

BAD_TOKENS = {
    "www", "app", "apps", "api", "jobs", "job", "careers", "career", "static", "assets",
    "cdn", "images", "img", "media", "embed", "boards", "sr-logo", "logo", "index", "en",
}

PATTERNS = [
    ("workday", r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
    ("greenhouse", r"(?:job-)?boards\.greenhouse\.io/(?:embed/job_board\?for=)?([a-zA-Z0-9_-]+)"),
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_-]+)"),
    ("lever", r"jobs\.(?:eu\.)?lever\.co/([a-zA-Z0-9_.-]+)"),
    ("ashby", r"jobs\.ashbyhq\.com/([a-zA-Z0-9_.-]+)"),
    ("workable", r"apply\.workable\.com/(?:api/v1/widget/accounts/)?([a-zA-Z0-9_-]+)"),
    ("recruitee", r"([a-zA-Z0-9_-]+)\.recruitee\.com"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([a-zA-Z0-9_-]+)"),
    ("teamtailor", r"([a-zA-Z0-9_-]+)\.teamtailor\.com"),
    ("personio", r"([a-zA-Z0-9_-]+)\.jobs\.personio\.(?:de|com)"),
    ("breezy", r"([a-zA-Z0-9_-]+)\.breezy\.hr"),
    ("bamboohr", r"([a-zA-Z0-9_-]+)\.bamboohr\.com"),
    ("rippling", r"ats\.rippling\.com/([a-zA-Z0-9_-]+)"),
]

LINK_HINT = re.compile(r"career|job|opening|vacan|position|hiring|join-us|work-with", re.I)
LINK_RE = re.compile(r'href="([^"]{2,300})"[^>]*>([^<]{0,80})', re.I)
