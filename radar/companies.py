import html
import re

from .net import fetch

LIST_URL = "https://remoteintech.company/companies/"
ITEM = re.compile(
    r'<div data-region="(.*?)" data-name="(.*?)" class="company-item">(.*?)</article></div>', re.S
)
NAME = re.compile(r'company-card__name"><a href=".*?">(.*?)</a>')
SITE = re.compile(r'company-card__website"><a href="(.*?)"')


def scrape(regions=None):
    body = fetch(LIST_URL, timeout=60)[1]
    out = []
    for region, slug, chunk in ITEM.findall(body):
        if regions and region not in regions:
            continue
        name = NAME.search(chunk)
        site = SITE.search(chunk)
        if not name or not site:
            continue
        out.append(
            {
                "slug": slug,
                "name": html.unescape(name.group(1)),
                "region": region,
                "careers_url": html.unescape(site.group(1)),
            }
        )
    if not out:
        raise RuntimeError("company list parsed to zero rows - page markup changed")
    return out
