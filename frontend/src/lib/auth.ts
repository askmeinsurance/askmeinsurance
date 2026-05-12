import type { Session } from '@supabase/supabase-js';
import type { AuthSession } from '../types/auth';

const AUTH_STORAGE_KEY = 'askmeinsurance_auth_session';

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

export function readAuthSession(): AuthSession | null {
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (!isNonEmptyString(parsed.accessToken)) {
      return null;
    }

    return {
      accessToken: parsed.accessToken.trim(),
      email: isNonEmptyString(parsed.email) ? parsed.email.trim() : undefined,
      refreshToken: isNonEmptyString(parsed.refreshToken) ? parsed.refreshToken.trim() : undefined,
      expiresAt: typeof parsed.expiresAt === 'number' ? parsed.expiresAt : undefined,
      source: parsed.source,
    };
  } catch {
    return null;
  }
}

export function saveAuthSession(session: AuthSession): void {
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearAuthSession(): void {
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function toAuthSessionFromSupabaseSession(session: Session): AuthSession {
  return {
    accessToken: session.access_token,
    refreshToken: session.refresh_token,
    expiresAt: session.expires_at,
    email: session.user.email,
    source: 'supabase',
  };
}
