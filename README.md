# job-radar

Daily crawl of the companies listed on [remoteintech.company](https://remoteintech.company/companies/),
into Postgres. Stores data/BI/solutions roles with their link, posting date, and the date the crawl
first saw them.

## Commands

    python -m radar.run --init                    # apply schema, load the company list
    python -m radar.run --resolve                 # find each company's job board (slow)
    python -m radar.run --resolve --dry-run --limit 20
    python -m radar.run                           # daily crawl

`SUPABASE_DB_URL` must be set for everything except `--dry-run`.

## Coverage

Of 528 companies whose region includes Europe, roughly 215 expose a public job board. The rest are
list rot — dead redirects, angel.co stubs, LinkedIn pages, marketing sites with a mailto. Headless
browser rendering was measured against those and found zero additional boards, so it is not used.

Supported boards: Greenhouse, Lever, Ashby, Workable, Recruitee, Personio, SmartRecruiters, Breezy,
Teamtailor, BambooHR, Rippling, Workday.

## Queries

    -- new since yesterday
    select c.name, p.title, p.location, p.url, p.posted_at
      from postings p join companies c on c.id = p.company_id
     where p.first_seen_at > now() - interval '1 day' and p.closed_at is null
     order by c.name;

    -- open roles in Spain
    select c.name, p.title, p.location, p.url
      from postings p join companies c on c.id = p.company_id
     where p.closed_at is null and p.location ~* 'spain|madrid|barcelona'
     order by p.first_seen_at desc;

## Filters

Both live in `config.toml`; only postings passing both are stored.

- `[titles]` — data/BI/solutions roles.
- `[locations]` — Europe only. The company regions on remoteintech describe where a company
  hires in general, not where a given job is, so US and APAC roles arrive on European-tagged
  boards and are dropped here. Locations are free text from each board, so these are string
  rules and never proof of work eligibility.
