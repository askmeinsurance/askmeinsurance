-- Supabase chatbot backend initial schema with RLS.
-- Safe to run multiple times where possible.

begin;

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

-- Indexes for common access patterns.
create index if not exists idx_conversations_user_id_created_at
  on public.conversations (user_id, created_at desc);

create index if not exists idx_messages_conversation_id_created_at
  on public.messages (conversation_id, created_at asc);

create index if not exists idx_messages_user_id_created_at
  on public.messages (user_id, created_at desc);

-- updated_at trigger.
drop trigger if exists trg_conversations_set_updated_at on public.conversations;
create trigger trg_conversations_set_updated_at
before update on public.conversations
for each row execute function public.set_updated_at();

-- Enable RLS.
alter table public.conversations enable row level security;
alter table public.messages enable row level security;

-- Conversations: owner full access.
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

-- Messages: owner full access.
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

commit;
