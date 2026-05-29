import { useMemo, useState } from 'react';
import { VerificationEmailSentModal } from './VerificationEmailSentModal';

interface AuthGateProps {
  onEmailPasswordSignIn?: (credentials: { email: string; password: string }) => void | Promise<void>;
  onEmailPasswordSignUp?: (credentials: { email: string; password: string }) => void | Promise<void>;
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
}: AuthGateProps) {
  const [mode, setMode] = useState<AuthMode>('signup');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<'email' | null>(null);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [verificationEmailSent, setVerificationEmailSent] = useState<string | null>(null);

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

  function switchMode(next: AuthMode) {
    setMode(next);
    setHasSubmitted(false);
    setErrorMessage(null);
  }

  async function handleEmailSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHasSubmitted(true);
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
      const code = (error as { code?: string }).code;
      if (code === 'EMAIL_VERIFICATION_REQUIRED') {
        setVerificationEmailSent(email.trim());
        return;
      }
      const rawMessage = error instanceof Error ? error.message : 'Authentication failed.';
      const normalized = rawMessage.toLowerCase();
      if (mode === 'signup' && normalized.includes('too many sign-up attempts')) {
        switchMode('signin');
        setErrorMessage('An account may already exist for this email. Please sign in to continue.');
      } else {
        setErrorMessage(rawMessage);
      }
    } finally {
      logAuthGate('Email auth submit finished');
      setActiveAction(null);
    }
  }

  return (
    <div className="auth-landing">
      {verificationEmailSent && (
        <VerificationEmailSentModal
          email={verificationEmailSent}
          onClose={() => {
            setVerificationEmailSent(null);
            switchMode('signin');
          }}
        />
      )}
      {/* Top-right social icons */}
      <div className="auth-social-icons">
        <a
          href="https://github.com/askmeinsurance/askmeinsurance"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-black/5 hover:text-gray-600"
          aria-label="GitHub"
        >
          <svg width="18" height="18" viewBox="0 0 98 96" fill="currentColor" aria-hidden="true">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M48.854 0C21.839 0 0 22 0 49.217c0 21.756 13.993 40.172 33.405 46.69 2.427.49 3.316-1.059 3.316-2.362 0-1.141-.08-5.052-.08-9.127-13.59 2.934-16.42-5.867-16.42-5.867-2.184-5.704-5.42-7.17-5.42-7.17-4.448-3.015.324-3.015.324-3.015 4.934.326 7.523 5.052 7.523 5.052 4.367 7.496 11.404 5.378 14.235 4.074.404-3.178 1.699-5.378 3.074-6.6-10.839-1.141-22.243-5.378-22.243-24.283 0-5.378 1.94-9.778 5.014-13.2-.485-1.222-2.184-6.275.486-13.038 0 0 4.125-1.304 13.426 5.052a46.97 46.97 0 0 1 12.214-1.63c4.125 0 8.33.571 12.213 1.63 9.302-6.356 13.427-5.052 13.427-5.052 2.67 6.763.97 11.816.485 13.038 3.155 3.422 5.015 7.822 5.015 13.2 0 18.905-11.404 23.06-22.324 24.283 1.78 1.548 3.316 4.481 3.316 9.126 0 6.6-.08 11.897-.08 13.526 0 1.304.89 2.853 3.316 2.364 19.412-6.52 33.405-24.935 33.405-46.691C97.707 22 75.788 0 48.854 0z"
            />
          </svg>
        </a>
        <a
          href="https://www.linkedin.com/in/joelkuanfeilee"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md p-1.5 text-gray-400 transition-colors hover:bg-black/5 hover:text-gray-600"
          aria-label="LinkedIn"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
          </svg>
        </a>
      </div>

      {/* Left: copywriting panel */}
      <div className="auth-left">
        <p className="auth-left-eyebrow">AskMeInsurance</p>
        <h1 className="auth-left-headline">Insurance help at your fingertips.</h1>
        <p className="auth-left-desc">
          AskMeInsurance helps customers navigate life insurance with confidence. Get instant answers to general insurance
          questions and policy-specific information through a secure, AI-powered conversational experience.
        </p>
        <hr className="auth-left-rule" />
      </div>

      {/* Right: login panel */}
      <div className="auth-right">
        <div className="auth-card w-full max-w-md rounded-3xl p-6 shadow-sm sm:p-8">
          <p className="auth-kicker text-xs font-semibold uppercase tracking-[0.24em]">AskMeInsurance</p>
          <h2 className="auth-headline mt-3 text-3xl leading-tight sm:text-4xl">
            {mode === 'signin' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="auth-subhead mt-3 text-sm sm:text-base">
            {mode === 'signin'
              ? 'Sign in with email to continue to your insurance workspace.'
              : 'Start with a secure account and keep your advice history in one place.'}
          </p>

          <div className="mt-7 grid grid-cols-2 gap-2 rounded-2xl bg-white/70 p-1 ring-1 ring-black/5">
            <button
              type="button"
              onClick={() => switchMode('signup')}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                mode === 'signup' ? 'bg-neutral-900 text-white shadow-sm' : 'text-neutral-700 hover:bg-neutral-100'
              }`}
              disabled={isBusy}
            >
              Sign Up
            </button>
            <button
              type="button"
              onClick={() => switchMode('signin')}
              className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                mode === 'signin' ? 'bg-neutral-900 text-white shadow-sm' : 'text-neutral-700 hover:bg-neutral-100'
              }`}
              disabled={isBusy}
            >
              Sign In
            </button>
          </div>

          <form className="mt-5 space-y-4" onSubmit={handleEmailSubmit}>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-neutral-700">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className={`w-full rounded-xl border px-3 py-2 text-sm text-neutral-900 outline-none transition ${
                  hasSubmitted && emailError ? 'border-red-400 focus:border-red-500' : 'border-neutral-300 focus:border-neutral-600'
                }`}
                placeholder="you@example.com"
                autoComplete="email"
                disabled={isBusy}
                aria-invalid={hasSubmitted && Boolean(emailError)}
              />
              {hasSubmitted && emailError && <p className="mt-1 text-xs text-red-600">{emailError}</p>}
            </label>

            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-neutral-700">Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className={`w-full rounded-xl border px-3 py-2 text-sm text-neutral-900 outline-none transition ${
                  hasSubmitted && passwordError ? 'border-red-400 focus:border-red-500' : 'border-neutral-300 focus:border-neutral-600'
                }`}
                placeholder="At least 8 characters"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                disabled={isBusy}
                aria-invalid={hasSubmitted && Boolean(passwordError)}
              />
              {hasSubmitted && passwordError && <p className="mt-1 text-xs text-red-600">{passwordError}</p>}
            </label>

            {mode === 'signup' && (
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-neutral-700">Confirm password</span>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  className={`w-full rounded-xl border px-3 py-2 text-sm text-neutral-900 outline-none transition ${
                    hasSubmitted && confirmPasswordError
                      ? 'border-red-400 focus:border-red-500'
                      : 'border-neutral-300 focus:border-neutral-600'
                  }`}
                  placeholder="Repeat your password"
                  autoComplete="new-password"
                  disabled={isBusy}
                  aria-invalid={hasSubmitted && Boolean(confirmPasswordError)}
                />
                {hasSubmitted && confirmPasswordError && <p className="mt-1 text-xs text-red-600">{confirmPasswordError}</p>}
              </label>
            )}

            {errorMessage && <p className="text-sm text-red-600">{errorMessage}</p>}

            <button
              type="submit"
              className="w-full rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isBusy}
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
    </div>
  );
}
