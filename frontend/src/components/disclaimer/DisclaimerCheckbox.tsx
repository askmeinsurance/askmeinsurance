interface DisclaimerCheckboxProps {
  agreed: boolean;
  onCheckboxClick: () => void;
}

export function DisclaimerCheckbox({ agreed, onCheckboxClick }: DisclaimerCheckboxProps) {
  return (
    <div className="flex items-center gap-2 mt-2">
      <button
        type="button"
        onClick={agreed ? undefined : onCheckboxClick}
        aria-label="Open portfolio disclaimer"
        className={`relative w-4 h-4 flex-shrink-0 rounded border flex items-center justify-center transition-colors before:absolute before:-inset-2 before:content-[''] ${
          agreed
            ? 'bg-neutral-900 border-neutral-900 cursor-default'
            : 'border-gray-300 bg-white hover:border-neutral-500 cursor-pointer'
        }`}
      >
        {agreed && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none" aria-hidden="true">
            <path
              d="M1 4L3.5 6.5L9 1"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>
      <span
        onClick={agreed ? undefined : onCheckboxClick}
        className={`text-xs text-gray-500 select-none ${agreed ? '' : 'cursor-pointer hover:text-gray-700'}`}
      >
        I agree to the terms and conditions
      </span>
    </div>
  );
}
