import json
import socket
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
RETRY_STATUS = {429, 500, 502, 503, 504}

# urlopen's timeout only bounds individual socket operations, so a server that
# accepts and then dribbles bytes can hold a worker forever. This bounds every
# socket the process opens.
socket.setdefaulttimeout(25)

# Pages are scanned with regexes; reading megabytes of marketing HTML costs far
# more in scanning than it ever yields in board links.
MAX_BODY = 600_000


def fetch(url, timeout=20, data=None, content_type=None, attempts=3):
    headers = {"User-Agent": UA}
    if content_type:
        headers["Content-Type"] = content_type
    last = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers=headers, data=data)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.geturl(), r.read(MAX_BODY).decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in RETRY_STATUS:
                raise
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise last


def fetch_json(url, **kw):
    return json.loads(fetch(url, **kw)[1])


def post_json(url, payload, **kw):
    return json.loads(
        fetch(url, data=json.dumps(payload).encode(), content_type="application/json", **kw)[1]
    )
