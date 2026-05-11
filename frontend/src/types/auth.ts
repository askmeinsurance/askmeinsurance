export type AuthSource = 'supabase';

export interface AuthSession {
  accessToken: string;
  email?: string;
  refreshToken?: string;
  expiresAt?: number;
  source?: AuthSource;
}

export interface AuthState {
  session: AuthSession | null;
  isReady: boolean;
}

export interface EmailPasswordCredentials {
  email: string;
  password: string;
}
