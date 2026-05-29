interface VerificationEmailSentModalProps {
  email: string;
  onClose: () => void;
}

export function VerificationEmailSentModal({ email, onClose }: VerificationEmailSentModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative w-full max-w-md mx-4 rounded-2xl bg-white shadow-xl p-6 flex flex-col gap-5">
        <div className="flex flex-col items-center gap-3 pt-2">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-neutral-100">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="text-neutral-700" aria-hidden="true">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="m2 7 10 7 10-7" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-900 text-center">Check your inbox</h2>
        </div>

        <p className="text-sm text-gray-600 leading-relaxed text-center">
          A verification link has been sent to <span className="font-medium text-gray-900">{email}</span>.
          Click the link to activate your account, then come back here to sign in.
        </p>

        <div className="h-px bg-gray-100" />

        <button
          type="button"
          onClick={onClose}
          className="w-full px-4 py-2.5 rounded-xl text-sm font-medium text-white bg-neutral-900 hover:bg-neutral-800 transition-colors"
        >
          Back to Sign In
        </button>
      </div>
    </div>
  );
}
