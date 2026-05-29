-- Remove tables and objects that have no corresponding application code.
-- Safe to run on existing deployments; IF EXISTS guards make it idempotent.
--
-- Drop order: policies referencing is_super_user() first, then the function,
-- then the backing table, then remaining orphaned tables.

begin;

-- Drop super_user RLS policies on tables we are keeping.
-- These reference is_super_user(), which must be dropped next.
drop policy if exists conversations_super_user_select_all on public.conversations;
drop policy if exists messages_super_user_select_all on public.messages;

-- Drop the is_super_user() helper.
-- The app reads is_super_user from JWT claims; it never queries user_roles.
drop function if exists public.is_super_user();

-- Drop orphaned tables. CASCADE removes their policies, indexes, and triggers.
drop table if exists public.user_roles cascade;
drop table if exists public.form_submissions cascade;
drop table if exists public.conversation_events cascade;
drop table if exists public.profiles cascade;

commit;
