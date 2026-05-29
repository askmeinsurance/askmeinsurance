import { useState, useRef, type KeyboardEvent } from 'react';
import { ArrowUp } from 'lucide-react';

interface ChatInputProps {
  value?: string;
  onChange?: (value: string) => void;
  onSubmit: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  placeholder = 'Ask InsureBot',
  disabled = false,
}: ChatInputProps) {
  const [internalValue, setInternalValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isControlled = value !== undefined && onChange !== undefined;
  const inputValue = isControlled ? value : internalValue;

  function handleChange(text: string) {
    if (isControlled) {
      onChange(text);
    } else {
      setInternalValue(text);
    }
    autoResize();
  }

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }

  function handleSubmit() {
    if (disabled) return;
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    if (!isControlled) {
      setInternalValue('');
      if (textareaRef.current) textareaRef.current.style.height = 'auto';
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  const canSubmit = !disabled && inputValue.trim().length > 0;

  return (
    <div className="flex items-center gap-2 w-full rounded-2xl border border-gray-200 bg-white px-3 py-2 shadow-sm focus-within:ring-2 focus-within:ring-neutral-600 focus-within:border-transparent">
      <textarea
        ref={textareaRef}
        rows={1}
        value={inputValue}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none resize-none overflow-y-auto disabled:cursor-not-allowed leading-5"
        style={{ maxHeight: '120px' }}
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!canSubmit}
        aria-label="Send message"
        className={`flex-shrink-0 p-1.5 rounded-full transition-colors ${
          canSubmit
            ? 'bg-neutral-900 text-white hover:bg-neutral-800'
            : 'bg-gray-100 text-gray-300 cursor-not-allowed'
        }`}
      >
        <ArrowUp size={16} />
      </button>
    </div>
  );
}
