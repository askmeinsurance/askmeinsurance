export interface AuthSession {
  accessToken: string;
  email?: string;
}

export interface AuthState {
  session: AuthSession | null;
  isReady: boolean;
}
