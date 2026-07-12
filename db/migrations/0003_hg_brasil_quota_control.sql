create table hg_brasil_quota_control (
    quota_date date primary key,
    requests_used integer not null default 0,
    daily_limit integer not null default 400,
    safety_margin numeric(3,2) not null default 0.90,
    effective_limit integer generated always as (floor(daily_limit * safety_margin)) stored,
    updated_at timestamptz not null default now()
);

create or replace function reserve_hg_brasil_quota(p_date date, p_n int)
returns integer
language plpgsql
set search_path = public
as $$
declare v_used integer;
begin
  insert into hg_brasil_quota_control (quota_date) values (p_date)
    on conflict (quota_date) do nothing;

  update hg_brasil_quota_control
     set requests_used = requests_used + p_n, updated_at = now()
   where quota_date = p_date
     and requests_used + p_n <= effective_limit
  returning requests_used into v_used;

  if v_used is null then
    raise exception 'QUOTA_EXCEEDED' using errcode = 'P0001';
  end if;
  return v_used;
end;
$$;
