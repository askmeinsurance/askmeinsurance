-- Per-user limit overrides. Application defaults apply when no row exists for a user.
-- No user-accessible RLS policies — service role only.
-- The set_updated_at() trigger function is reused from 001_init.sql.

begin;

create table if not exists public.user_limits (
  user_id           uuid primary key references auth.users(id) on delete cascade,
  max_conversations int not null default 10,
  max_messages      int not null default 100,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

drop trigger if exists trg_user_limits_set_updated_at on public.user_limits;
create trigger trg_user_limits_set_updated_at
before update on public.user_limits
for each row execute function public.set_updated_at();

-- RLS enabled with no policies = authenticated users have zero access;
-- service role bypasses RLS by default in Supabase.
alter table public.user_limits enable row level security;

commit;
