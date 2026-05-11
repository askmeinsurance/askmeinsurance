import type { Session } from '@supabase/supabase-js';
import type { AuthSession, EmailPasswordCredentials } from '../types/auth';

const AUTH_STORAGE_KEY = 'askmeinsurance_auth_session';

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function resolveApiBase(): string {
  const configured = import.meta.env.VITE_BACKEND_BASE_URL?.trim().replace(/\/+$/, '');
  if (configured) {
    return `${configured}/api/v1`;
  }

  if (import.meta.env.DEV && typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000/api/v1`;
  }

  return '/api/v1';
}

export function isDevAuthEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_DEV_AUTH?.trim().toLowerCase() === 'true';
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

function normalizeAccessToken(payload: Record<string, unknown>): string | null {
  const tokenCandidates = [payload.access_token, payload.token, payload.accessToken];
  const found = tokenCandidates.find((value) => isNonEmptyString(value));
  return found ? (found as string).trim() : null;
}

function normalizeEmail(payload: Record<string, unknown>, fallback: string): string | undefined {
  const payloadEmail = payload.email;
  if (isNonEmptyString(payloadEmail)) {
    return payloadEmail.trim();
  }
  return fallback.trim() || undefined;
}

export async function loginWithDevApi(credentials: EmailPasswordCredentials): Promise<AuthSession> {
  const response = await fetch(`${resolveApiBase()}/auth/dev-login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    const err = new Error(`Dev login failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }

  const payload = (await response.json()) as Record<string, unknown>;
  const accessToken = normalizeAccessToken(payload);

  if (!accessToken) {
    throw new Error('Dev login response did not include an access token');
  }

  return {
    accessToken,
    email: normalizeEmail(payload, credentials.email),
    source: 'dev-login',
  };
}
