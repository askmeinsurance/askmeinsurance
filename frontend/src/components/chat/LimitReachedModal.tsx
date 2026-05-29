import { LIMIT_MODAL_CONFIG } from '../../config/limitModal';

interface LimitReachedModalProps {
  onClose: () => void;
}

export function LimitReachedModal({ onClose }: LimitReachedModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-sm mx-4 rounded-2xl bg-white shadow-xl p-6 flex flex-col gap-5">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold text-gray-900">{LIMIT_MODAL_CONFIG.title}</h2>
          <div className="h-px bg-gray-100 mt-1" />
        </div>

        <p className="text-sm text-gray-600 leading-relaxed">{LIMIT_MODAL_CONFIG.body}</p>

        <div className="flex gap-3">
          {LIMIT_MODAL_CONFIG.links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium text-center text-white bg-neutral-900 hover:bg-neutral-700 transition-colors"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="flex justify-end pt-1">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            {LIMIT_MODAL_CONFIG.closeLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
