create table if not exists companies (
    id                 bigserial primary key,
    slug               text unique not null,
    name               text not null,
    region             text,
    careers_url        text,
    ats                text,
    token              text,
    resolved_at        timestamptz,
    last_ok_at         timestamptz,
    resolve_fail_count int not null default 0
);

create table if not exists postings (
    id            bigserial primary key,
    company_id    bigint not null references companies (id) on delete cascade,
    ats_job_id    text not null,
    title         text not null,
    location      text,
    url           text,
    posted_at     date,
    first_seen_at timestamptz not null default now(),
    last_seen_at  timestamptz not null default now(),
    closed_at     timestamptz,
    unique (company_id, ats_job_id)
);

create index if not exists postings_first_seen_idx on postings (first_seen_at desc);
create index if not exists postings_open_idx on postings (closed_at) where closed_at is null;

create table if not exists runs (
    id                bigserial primary key,
    started_at        timestamptz not null default now(),
    finished_at       timestamptz,
    companies_queried int,
    postings_seen     int,
    postings_new      int,
    errors            jsonb
);
