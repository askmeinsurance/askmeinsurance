-- Set or update limits for a specific user by their UUID.
-- Run as service role in the Supabase SQL editor.
-- Replace <USER_UUID> with the UUID from auth.users (visible in Supabase Auth dashboard).

insert into public.user_limits (user_id, max_conversations, max_messages)
values ('<USER_UUID>', 10, 100)
on conflict (user_id)
do update set
    max_conversations = excluded.max_conversations,
    max_messages      = excluded.max_messages,
    updated_at        = now();

-- To reset a user back to global defaults, delete their override row:
-- delete from public.user_limits where user_id = '<USER_UUID>';

-- To inspect all current limit overrides:
-- select * from public.user_limits order by created_at desc;
