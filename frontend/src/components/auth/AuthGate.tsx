import { useMemo, useState } from 'react';

interface AuthGateProps {
  onEmailPasswordSignIn?: (credentials: { email: string; password: string }) => void | Promise<void>;
  onEmailPasswordSignUp?: (credentials: { email: string; password: string }) => void | Promise<void>;
  onGoogleSignIn?: () => void | Promise<void>;
}

type AuthMode = 'signin' | 'signup';

function logAuthGate(message: string, details?: unknown) {
  if (details === undefined) {
    console.log(`[AuthGate] ${message}`);
    return;
  }
  console.log(`[AuthGate] ${message}`, details);
}

export function AuthGate({
  onEmailPasswordSignIn,
  onEmailPasswordSignUp,
  onGoogleSignIn,
}: AuthGateProps) {
  const [mode, setMode] = useState<AuthMode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<'email' | 'google' | null>(null);

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
    logAuthGate('Email auth submit triggered', {
      mode,
      emailLength: email.trim().length,
      hasPassword: Boolean(password),
      hasConfirmPassword: Boolean(confirmPassword),
    });

    if (!canSubmitEmail) {
      logAuthGate('Email auth submit blocked by validation', {
        emailError,
        passwordError,
        confirmPasswordError,
      });
      setErrorMessage('Please correct the highlighted fields.');
      return;
    }

    setActiveAction('email');
    try {
      if (mode === 'signup') {
        if (onEmailPasswordSignUp) {
          logAuthGate('Calling signup handler');
          await onEmailPasswordSignUp({ email: email.trim(), password });
          logAuthGate('Signup handler resolved');
        }
      } else if (onEmailPasswordSignIn) {
        logAuthGate('Calling signin handler');
        await onEmailPasswordSignIn({ email: email.trim(), password });
        logAuthGate('Signin handler resolved');
      }
    } catch (error) {
      logAuthGate('Email auth submit failed', error);
      const rawMessage = error instanceof Error ? error.message : 'Authentication failed.';
      const normalized = rawMessage.toLowerCase();
      if (mode === 'signup' && normalized.includes('too many sign-up attempts')) {
        setMode('signin');
        setErrorMessage('An account may already exist for this email. Please sign in to continue.');
      } else {
        setErrorMessage(rawMessage);
      }
    } finally {
      logAuthGate('Email auth submit finished');
      setActiveAction(null);
    }
  }

  async function handleGoogleAction() {
    setErrorMessage(null);
    setActiveAction('google');
    logAuthGate('Google auth flow triggered');
    try {
      if (onGoogleSignIn) {
        await onGoogleSignIn();
        logAuthGate('Google auth handler resolved');
      }
    } catch (error) {
      logAuthGate('Google auth failed', error);
      setErrorMessage(error instanceof Error ? error.message : 'Google authentication failed.');
    } finally {
      logAuthGate('Google auth flow finished');
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

      </div>
    </div>
  );
}
