"""Static HTML view of open postings - an alternative to querying Postgres by hand."""
import html
import re
from datetime import datetime, timedelta, timezone

NEW_WINDOW = timedelta(days=1)
REMOTE_RE = re.compile(r"\bremote\b|\banywhere\b|\bworldwide\b|home.?based|distributed", re.I)
HYBRID_RE = re.compile(r"\bhybrid\b", re.I)


def _work_mode(location):
    if not location:
        return ""
    if HYBRID_RE.search(location):
        return "Hybrid"
    if REMOTE_RE.search(location):
        return "Remote"
    return ""


def render_html(rows, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc)
    new_cutoff = generated_at - NEW_WINDOW

    def esc(s):
        return html.escape(str(s or ""))

    trs = []
    for r in rows:
        is_new = r["first_seen_at"] and r["first_seen_at"] > new_cutoff
        mode = _work_mode(r["location"])
        trs.append(
            f"""<tr class="{'new' if is_new else ''}">
  <td>{esc(r['company'])}</td>
  <td><a href="{esc(r['url'])}" target="_blank" rel="noopener">{esc(r['title'])}</a></td>
  <td>{esc(r['location'])}</td>
  <td>{f'<span class="mode {mode.lower()}">{mode}</span>' if mode else ''}</td>
  <td>{esc(r['posted_at'] or '')}</td>
</tr>"""
        )

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>job-radar</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0b0d10; color: #e6e6e6; }}
  h1 {{ font-size: 1.1rem; font-weight: 500; color: #9aa0a6; margin-bottom: 1rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: .5rem .75rem; border-bottom: 1px solid #2a2d33; }}
  th {{ color: #9aa0a6; font-weight: 500; }}
  tr.new td {{ background: #16321f; }}
  a {{ color: #7ab8ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .mode {{ font-size: .8rem; padding: .1rem .5rem; border-radius: 1rem; white-space: nowrap; }}
  .mode.remote {{ background: #17324d; color: #7ab8ff; }}
  .mode.hybrid {{ background: #3d2f14; color: #e0b354; }}
</style>
</head>
<body>
<h1>job-radar &mdash; {len(rows)} open postings, generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}</h1>
<table>
<tr><th>Company</th><th>Title</th><th>Location</th><th>Mode</th><th>Posted</th></tr>
{''.join(trs)}
</table>
</body>
</html>
"""


def main(path="postings.html"):
    from . import db

    with db.connect() as conn:
        rows = db.open_postings(conn)
    with open(path, "w") as f:
        f.write(render_html(rows))
    print(f"{len(rows)} open postings -> {path}")
