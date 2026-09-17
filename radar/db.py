import json
import os

import psycopg
from psycopg.rows import dict_row


def connect():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    # prepare_threshold=None: the Supabase pooler runs pgbouncer in transaction
    # mode, which routes each transaction to a different backend, so server-side
    # prepared statements (psycopg's default) don't survive - "prepared statement
    # already exists" errors otherwise.
    return psycopg.connect(url, row_factory=dict_row, autocommit=True, prepare_threshold=None)


def apply_schema(conn, path="schema.sql"):
    with open(path) as f:
        conn.execute(f.read())


def upsert_companies(conn, rows):
    # Looped execute(), not executemany(): executemany() always runs through
    # psycopg's pipeline mode, which forces server-side prepared statements
    # regardless of prepare_threshold - incompatible with the pooler.
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                insert into companies (slug, name, region, careers_url)
                values (%(slug)s, %(name)s, %(region)s, %(careers_url)s)
                on conflict (slug) do update
                  set name = excluded.name,
                      region = excluded.region,
                      careers_url = excluded.careers_url
                """,
                row,
            )


def companies_to_resolve(conn, limit=None, only_unresolved=True):
    sql = "select id, slug, name, careers_url from companies"
    if only_unresolved:
        sql += " where ats is null"
    sql += " order by resolve_fail_count, id"
    if limit:
        sql += f" limit {int(limit)}"
    return conn.execute(sql).fetchall()


def save_resolution(conn, company_id, ats, token):
    if ats:
        conn.execute(
            "update companies set ats=%s, token=%s, resolved_at=now(), resolve_fail_count=0"
            " where id=%s",
            (ats, token, company_id),
        )
    else:
        conn.execute(
            "update companies set resolve_fail_count = resolve_fail_count + 1 where id=%s",
            (company_id,),
        )


def resolved_companies(conn):
    return conn.execute(
        "select id, name, ats, token from companies where ats is not null and token is not null"
        " order by id"
    ).fetchall()


def upsert_postings(conn, company_id, jobs):
    """Returns the number of rows that were newly inserted."""
    if not jobs:
        return 0
    inserted = 0
    with conn.cursor() as cur:
        for j in jobs:
            cur.execute(
                """
                insert into postings
                    (company_id, ats_job_id, title, location, url, posted_at)
                values
                    (%(company_id)s, %(ats_job_id)s, %(title)s, %(location)s, %(url)s, %(posted_at)s)
                on conflict (company_id, ats_job_id) do update
                  set last_seen_at = now(),
                      title = excluded.title,
                      location = excluded.location,
                      url = excluded.url,
                      closed_at = null
                returning (xmax = 0) as inserted
                """,
                dict(j, company_id=company_id),
            )
            row = cur.fetchone()
            if row and row["inserted"]:
                inserted += 1
    return inserted


def close_stale(conn, company_ids, run_started):
    """Mark postings closed after two consecutive runs of absence."""
    if not company_ids:
        return 0
    return conn.execute(
        """
        update postings set closed_at = now()
         where company_id = any(%s)
           and closed_at is null
           and last_seen_at < %s - interval '20 hours'
        """,
        (list(company_ids), run_started),
    ).rowcount


def purge_stale(conn, max_age_days, keep_undated):
    """Postings age out of the table entirely - a role too old to apply for is noise.
    Boards that expose no date are aged from when this crawler first saw them."""
    undated = (
        "(posted_at is null and first_seen_at < now() - make_interval(days => %(days)s))"
        if keep_undated
        else "posted_at is null"
    )
    return conn.execute(
        f"""
        delete from postings
         where (posted_at is not null and posted_at < current_date - %(days)s)
            or {undated}
        """,
        {"days": max_age_days},
    ).rowcount


def start_run(conn):
    return conn.execute("insert into runs (started_at) values (now()) returning id").fetchone()["id"]


def finish_run(conn, run_id, queried, seen, new, errors):
    conn.execute(
        """
        update runs set finished_at=now(), companies_queried=%s, postings_seen=%s,
                        postings_new=%s, errors=%s
         where id=%s
        """,
        (queried, seen, new, json.dumps(errors), run_id),
    )


def open_postings(conn):
    return conn.execute(
        """
        select c.name as company, p.title, p.location, p.url, p.posted_at, p.first_seen_at
          from postings p join companies c on c.id = p.company_id
         where p.closed_at is null
         order by p.first_seen_at desc
        """
    ).fetchall()


def recent_average_seen(conn, days=7):
    row = conn.execute(
        """
        select avg(postings_seen)::float as avg_seen
          from runs
         where finished_at is not null
           and started_at > now() - make_interval(days => %s)
           and postings_seen > 0
        """,
        (days,),
    ).fetchone()
    return row["avg_seen"]
