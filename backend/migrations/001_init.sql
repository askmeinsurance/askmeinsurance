-- Supabase chatbot backend initial schema with RLS + RBAC (super_user)
-- Safe to run multiple times where possible.

begin;

create extension if not exists pgcrypto;

-- Utility trigger function to keep updated_at in sync.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- User profile linked 1:1 with auth.users.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  phone text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Conversation owned by a user.
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  status text not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz
);

-- Messages inside a conversation.
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  sender text not null check (sender in ('user', 'assistant', 'system')),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Event stream for analytics/audit.
create table if not exists public.conversation_events (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Structured forms submitted during/after conversation.
create table if not exists public.form_submissions (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.conversations(id) on delete set null,
  user_id uuid not null references auth.users(id) on delete cascade,
  form_type text not null,
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- RBAC roles for a user. Keep extensible but currently centered on super_user.
create table if not exists public.user_roles (
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, role),
  constraint user_roles_role_check check (role in ('super_user'))
);

-- RBAC helper: true when the current auth user has super_user role.
create or replace function public.is_super_user()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.user_roles ur
    where ur.user_id = auth.uid()
      and ur.role = 'super_user'
  );
$$;

-- Helpful indexes for common access patterns.
create index if not exists idx_conversations_user_id_created_at
  on public.conversations (user_id, created_at desc);

create index if not exists idx_messages_conversation_id_created_at
  on public.messages (conversation_id, created_at asc);

create index if not exists idx_messages_user_id_created_at
  on public.messages (user_id, created_at desc);

create index if not exists idx_conversation_events_conversation_id_created_at
  on public.conversation_events (conversation_id, created_at desc);

create index if not exists idx_conversation_events_user_id_created_at
  on public.conversation_events (user_id, created_at desc);

create index if not exists idx_form_submissions_user_id_created_at
  on public.form_submissions (user_id, created_at desc);

create index if not exists idx_form_submissions_conversation_id_created_at
  on public.form_submissions (conversation_id, created_at desc)
  where conversation_id is not null;

create index if not exists idx_user_roles_role_user_id
  on public.user_roles (role, user_id);

-- updated_at triggers (explicitly required for profiles/conversations).
drop trigger if exists trg_profiles_set_updated_at on public.profiles;
create trigger trg_profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists trg_conversations_set_updated_at on public.conversations;
create trigger trg_conversations_set_updated_at
before update on public.conversations
for each row execute function public.set_updated_at();

-- Optional, useful for form_submissions consistency.
drop trigger if exists trg_form_submissions_set_updated_at on public.form_submissions;
create trigger trg_form_submissions_set_updated_at
before update on public.form_submissions
for each row execute function public.set_updated_at();

-- Enable RLS on all app tables.
alter table public.profiles enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.conversation_events enable row level security;
alter table public.form_submissions enable row level security;
alter table public.user_roles enable row level security;

-- Profiles: owner full access, super_user read-all.
drop policy if exists profiles_owner_select on public.profiles;
create policy profiles_owner_select on public.profiles
for select using (id = auth.uid());

drop policy if exists profiles_owner_insert on public.profiles;
create policy profiles_owner_insert on public.profiles
for insert with check (id = auth.uid());

drop policy if exists profiles_owner_update on public.profiles;
create policy profiles_owner_update on public.profiles
for update using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists profiles_owner_delete on public.profiles;
create policy profiles_owner_delete on public.profiles
for delete using (id = auth.uid());

drop policy if exists profiles_super_user_select_all on public.profiles;
create policy profiles_super_user_select_all on public.profiles
for select using (public.is_super_user());

-- Conversations: owner full access, super_user read-all.
drop policy if exists conversations_owner_select on public.conversations;
create policy conversations_owner_select on public.conversations
for select using (user_id = auth.uid());

drop policy if exists conversations_owner_insert on public.conversations;
create policy conversations_owner_insert on public.conversations
for insert with check (user_id = auth.uid());

drop policy if exists conversations_owner_update on public.conversations;
create policy conversations_owner_update on public.conversations
for update using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists conversations_owner_delete on public.conversations;
create policy conversations_owner_delete on public.conversations
for delete using (user_id = auth.uid());

drop policy if exists conversations_super_user_select_all on public.conversations;
create policy conversations_super_user_select_all on public.conversations
for select using (public.is_super_user());

-- Messages: owner full access by row user_id, plus super_user read-all.
drop policy if exists messages_owner_select on public.messages;
create policy messages_owner_select on public.messages
for select using (user_id = auth.uid());

drop policy if exists messages_owner_insert on public.messages;
create policy messages_owner_insert on public.messages
for insert with check (user_id = auth.uid());

drop policy if exists messages_owner_update on public.messages;
create policy messages_owner_update on public.messages
for update using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists messages_owner_delete on public.messages;
create policy messages_owner_delete on public.messages
for delete using (user_id = auth.uid());

drop policy if exists messages_super_user_select_all on public.messages;
create policy messages_super_user_select_all on public.messages
for select using (public.is_super_user());

-- Conversation events: owner full access by row user_id, plus super_user read-all.
drop policy if exists conversation_events_owner_select on public.conversation_events;
create policy conversation_events_owner_select on public.conversation_events
for select using (user_id = auth.uid());

drop policy if exists conversation_events_owner_insert on public.conversation_events;
create policy conversation_events_owner_insert on public.conversation_events
for insert with check (user_id = auth.uid());

drop policy if exists conversation_events_owner_update on public.conversation_events;
create policy conversation_events_owner_update on public.conversation_events
for update using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists conversation_events_owner_delete on public.conversation_events;
create policy conversation_events_owner_delete on public.conversation_events
for delete using (user_id = auth.uid());

drop policy if exists conversation_events_super_user_select_all on public.conversation_events;
create policy conversation_events_super_user_select_all on public.conversation_events
for select using (public.is_super_user());

-- Form submissions: owner full access, super_user read-all.
drop policy if exists form_submissions_owner_select on public.form_submissions;
create policy form_submissions_owner_select on public.form_submissions
for select using (user_id = auth.uid());

drop policy if exists form_submissions_owner_insert on public.form_submissions;
create policy form_submissions_owner_insert on public.form_submissions
for insert with check (user_id = auth.uid());

drop policy if exists form_submissions_owner_update on public.form_submissions;
create policy form_submissions_owner_update on public.form_submissions
for update using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists form_submissions_owner_delete on public.form_submissions;
create policy form_submissions_owner_delete on public.form_submissions
for delete using (user_id = auth.uid());

drop policy if exists form_submissions_super_user_select_all on public.form_submissions;
create policy form_submissions_super_user_select_all on public.form_submissions
for select using (public.is_super_user());

-- user_roles: users can read their own roles; super_user can read all and manage rows.
drop policy if exists user_roles_self_select on public.user_roles;
create policy user_roles_self_select on public.user_roles
for select using (user_id = auth.uid());

drop policy if exists user_roles_super_user_select_all on public.user_roles;
create policy user_roles_super_user_select_all on public.user_roles
for select using (public.is_super_user());

drop policy if exists user_roles_super_user_insert on public.user_roles;
create policy user_roles_super_user_insert on public.user_roles
for insert with check (public.is_super_user());

drop policy if exists user_roles_super_user_update on public.user_roles;
create policy user_roles_super_user_update on public.user_roles
for update using (public.is_super_user()) with check (public.is_super_user());

drop policy if exists user_roles_super_user_delete on public.user_roles;
create policy user_roles_super_user_delete on public.user_roles
for delete using (public.is_super_user());

commit;
