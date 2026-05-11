import { useState } from 'react';

interface AuthGateProps {
  onSignIn: (token: string, email?: string) => void;
}

export function AuthGate({ onSignIn }: AuthGateProps) {
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedToken = token.trim();
    if (!normalizedToken) {
      setError('Access token is required.');
      return;
    }

    setError(null);
    onSignIn(normalizedToken, email.trim() || undefined);
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center px-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500">AskMeInsurance</p>
        <h1 className="mt-2 text-2xl font-semibold text-gray-900">Sign in to access chat</h1>
        <p className="mt-2 text-sm text-gray-600">
          Enter your bearer token to access protected chat APIs.
        </p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-gray-700">Email (optional)</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-gray-500"
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-gray-700">Bearer token</span>
            <textarea
              value={token}
              onChange={(event) => setToken(event.target.value)}
              className="min-h-[112px] w-full rounded-xl border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-gray-500"
              placeholder="Paste your access token"
              autoComplete="off"
            />
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            className="w-full rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800"
          >
            Continue
          </button>
        </form>
      </div>
    </div>
  );
}
