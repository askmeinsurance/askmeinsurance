import { useMemo, useState } from 'react';

interface AuthGateProps {
  onSignIn?: (token: string, email?: string) => void | Promise<void>;
  onEmailPasswordSignIn?: (credentials: { email: string; password: string }) => void | Promise<void>;
  onEmailPasswordSignUp?: (credentials: { email: string; password: string }) => void | Promise<void>;
  onGoogleSignIn?: () => void | Promise<void>;
  onDevLogin?: (credentials: { email: string; password: string }) => void | Promise<void>;
  devAuthEnabled?: boolean;
}

type AuthMode = 'signin' | 'signup';

export function AuthGate({
  onSignIn,
  onEmailPasswordSignIn,
  onEmailPasswordSignUp,
  onGoogleSignIn,
  onDevLogin,
  devAuthEnabled,
}: AuthGateProps) {
  const [mode, setMode] = useState<AuthMode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<'email' | 'google' | 'dev' | null>(null);
  const [isDevOpen, setIsDevOpen] = useState(false);

  const isDevAuthEnabled = useMemo(() => {
    if (typeof devAuthEnabled === 'boolean') {
      return devAuthEnabled;
    }

    return String(import.meta.env.VITE_ENABLE_DEV_AUTH ?? '').toLowerCase() === 'true';
  }, [devAuthEnabled]);

  const emailError = useMemo(() => {
    if (!email.trim()) {
      return 'Email is required.';
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      return 'Enter a valid email address.';
    }

    return null;
  }, [email]);

  const passwordError = useMemo(() => {
    if (!password) {
      return 'Password is required.';
    }

    if (password.length < 8) {
      return 'Password must be at least 8 characters.';
    }

    return null;
  }, [password]);

  const confirmPasswordError = useMemo(() => {
    if (mode !== 'signup') {
      return null;
    }

    if (!confirmPassword) {
      return 'Please confirm your password.';
    }

    if (password !== confirmPassword) {
      return 'Passwords do not match.';
    }

    return null;
  }, [confirmPassword, mode, password]);

  const canSubmitEmail = !emailError && !passwordError && !confirmPasswordError;
  const isBusy = activeAction !== null;

  async function handleEmailSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);

    if (!canSubmitEmail) {
      setErrorMessage('Please correct the highlighted fields.');
      return;
    }

    setActiveAction('email');
    try {
      if (mode === 'signup') {
        if (onEmailPasswordSignUp) {
          await onEmailPasswordSignUp({ email: email.trim(), password });
        } else if (onSignIn) {
          await onSignIn(password, email.trim());
        }
      } else if (onEmailPasswordSignIn) {
        await onEmailPasswordSignIn({ email: email.trim(), password });
      } else if (onSignIn) {
        await onSignIn(password, email.trim());
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Authentication failed.');
    } finally {
      setActiveAction(null);
    }
  }

  async function handleGoogleAction() {
    setErrorMessage(null);
    setActiveAction('google');
    try {
      if (onGoogleSignIn) {
        await onGoogleSignIn();
      } else if (onSignIn) {
        await onSignIn(`google:${mode}`, email.trim() || undefined);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Google authentication failed.');
    } finally {
      setActiveAction(null);
    }
  }

  async function handleDevAccess() {
    if (!email.trim() || !password) {
      setErrorMessage('Dev email and password are required.');
      return;
    }

    setErrorMessage(null);
    setActiveAction('dev');
    try {
      if (onDevLogin) {
        await onDevLogin({ email: email.trim(), password });
      } else if (onSignIn) {
        await onSignIn(password, email.trim() || undefined);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Dev access failed.');
    } finally {
      setActiveAction(null);
    }
  }

  return (
    <div className="auth-shell flex min-h-screen w-full items-center justify-center px-4 py-8 sm:px-6">
      <div className="auth-card w-full max-w-xl rounded-3xl p-6 shadow-sm sm:p-8">
        <p className="auth-kicker text-xs font-semibold uppercase tracking-[0.24em]">AskMeInsurance</p>
        <h1 className="auth-headline mt-3 text-3xl leading-tight sm:text-4xl">
          {mode === 'signin' ? 'Welcome back' : 'Create your account'}
        </h1>
        <p className="auth-subhead mt-3 text-sm sm:text-base">
          {mode === 'signin'
            ? 'Sign in with Google or email to continue to your insurance workspace.'
            : 'Start with a secure account and keep your advice history in one place.'}
        </p>

        <div className="mt-7 grid grid-cols-2 gap-2 rounded-2xl bg-white/70 p-1 ring-1 ring-black/5">
          <button
            type="button"
            onClick={() => setMode('signin')}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              mode === 'signin' ? 'bg-neutral-900 text-white shadow-sm' : 'text-neutral-700 hover:bg-neutral-100'
            }`}
            disabled={isBusy}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => setMode('signup')}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              mode === 'signup' ? 'bg-neutral-900 text-white shadow-sm' : 'text-neutral-700 hover:bg-neutral-100'
            }`}
            disabled={isBusy}
          >
            Sign Up
          </button>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            className="rounded-xl border border-neutral-300 bg-white px-4 py-2.5 text-sm font-medium text-neutral-900 transition hover:border-neutral-500 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleGoogleAction}
            disabled={isBusy}
          >
            {activeAction === 'google' ? 'Connecting Google...' : `Continue with Google`}
          </button>
          <div className="rounded-xl border border-dashed border-neutral-300 px-4 py-2.5 text-sm text-neutral-500">
            or use email and password
          </div>
        </div>

        <form className="mt-5 space-y-4" onSubmit={handleEmailSubmit}>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-neutral-700">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={`w-full rounded-xl border px-3 py-2 text-sm text-neutral-900 outline-none transition ${
                emailError ? 'border-red-400 focus:border-red-500' : 'border-neutral-300 focus:border-neutral-600'
              }`}
              placeholder="you@example.com"
              autoComplete="email"
              disabled={isBusy}
              aria-invalid={Boolean(emailError)}
            />
            {emailError && <p className="mt-1 text-xs text-red-600">{emailError}</p>}
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-neutral-700">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={`w-full rounded-xl border px-3 py-2 text-sm text-neutral-900 outline-none transition ${
                passwordError ? 'border-red-400 focus:border-red-500' : 'border-neutral-300 focus:border-neutral-600'
              }`}
              placeholder="At least 8 characters"
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              disabled={isBusy}
              aria-invalid={Boolean(passwordError)}
            />
            {passwordError && <p className="mt-1 text-xs text-red-600">{passwordError}</p>}
          </label>

          {mode === 'signup' && (
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-neutral-700">Confirm password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className={`w-full rounded-xl border px-3 py-2 text-sm text-neutral-900 outline-none transition ${
                  confirmPasswordError
                    ? 'border-red-400 focus:border-red-500'
                    : 'border-neutral-300 focus:border-neutral-600'
                }`}
                placeholder="Repeat your password"
                autoComplete="new-password"
                disabled={isBusy}
                aria-invalid={Boolean(confirmPasswordError)}
              />
              {confirmPasswordError && <p className="mt-1 text-xs text-red-600">{confirmPasswordError}</p>}
            </label>
          )}

          {errorMessage && <p className="text-sm text-red-600">{errorMessage}</p>}

          <button
            type="submit"
            className="w-full rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isBusy || !canSubmitEmail}
          >
            {activeAction === 'email'
              ? mode === 'signin'
                ? 'Signing In...'
                : 'Creating Account...'
              : mode === 'signin'
                ? 'Sign In with Email'
                : 'Create Account'}
          </button>
        </form>

        {isDevAuthEnabled && (
          <details
            className="mt-5 rounded-2xl border border-neutral-200 bg-white/70 p-4"
            open={isDevOpen}
            onToggle={(event) => setIsDevOpen((event.target as HTMLDetailsElement).open)}
          >
            <summary className="cursor-pointer text-sm font-medium text-neutral-700">Dev access</summary>
            <p className="mt-2 text-xs text-neutral-500">Use dev superuser email/password for local development only.</p>
            <button
              type="button"
              className="mt-3 rounded-xl border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-900 transition hover:border-neutral-500 disabled:cursor-not-allowed disabled:opacity-60"
              onClick={handleDevAccess}
              disabled={isBusy}
            >
              {activeAction === 'dev' ? 'Authorizing...' : 'Continue with Dev Access'}
            </button>
          </details>
        )}
      </div>
    </div>
  );
}
