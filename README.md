# job-radar

Daily crawl into Postgres, from two company sources:
[remoteintech.company](https://remoteintech.company/companies/) (companies that hire remotely,
mostly Europe-facing) and `sources/target-companies.md` (a curated list of Databricks/Tableau/
Snowflake customers - companies already running Fran's tool stack). Stores data/BI/solutions
roles with their link, posting date, and the date the crawl first saw them.

## Commands

    python -m radar.run --init                    # apply schema, load both company sources
    python -m radar.run --resolve                 # find each company's job board (slow)
    python -m radar.run --resolve --dry-run --limit 20
    python -m radar.run                           # daily crawl
    python -m radar.run --report [PATH]           # write open postings to a static HTML page (default postings.html)

`SUPABASE_DB_URL` must be set for everything except `--dry-run`.

## Coverage

Of 528 remoteintech.company companies whose region includes Europe, roughly 215 expose a public
job board. The rest are list rot — dead redirects, angel.co stubs, LinkedIn pages, marketing
sites with a mailto. Headless browser rendering was measured against those and found zero
additional boards, so it is not used.

The tool-vendor list (`sources/target-companies.md`, ~230 companies) has no per-company careers
URL - it's names scraped off vendor case-study pages, not board links. Each one gets a guessed
domain (`{name}.com`) and a fallback slug-probe against Greenhouse/Ashby/Lever; large enterprises
on Workday or a bespoke ATS mostly won't resolve this way (see `sources/job-leads-pilot.md` for
manually-confirmed examples like Adobe and Charles Schwab that this crawler won't catch without
more work). Treat its resolution rate as lower than remoteintech's by design, not a bug.

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
- `[freshness]` — nothing older than 20 days. Old rows are also deleted from the table on
  every run, so the table only ever holds roles still worth applying for. Workday, BambooHR
  and Rippling expose no posting date; those are aged from when the crawler first saw them
  (`keep_undated = false` drops them instead).
- `[locations]` — Europe only, regardless of company source. A US company in the tool-vendor
  list is fine; a US-based *posting* from it is not - only remote/worldwide roles or roles in
  Europe (Madrid/Spain included) pass. The company regions on remoteintech describe where a
  company hires in general, not where a given job is, so non-European roles arrive on
  European-tagged boards and are dropped here too. Locations are free text from each board, so
  these are string rules and never proof of work eligibility.
