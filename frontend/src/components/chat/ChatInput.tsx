import { useState, type KeyboardEvent } from 'react';
import { ArrowUp, Plus } from 'lucide-react';

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

  const isControlled = value !== undefined && onChange !== undefined;
  const inputValue = isControlled ? value : internalValue;

  function handleChange(text: string) {
    if (isControlled) {
      onChange(text);
    } else {
      setInternalValue(text);
    }
  }

  function handleSubmit() {
    if (disabled) return;
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    if (!isControlled) {
      setInternalValue('');
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  const canSubmit = !disabled && inputValue.trim().length > 0;

  return (
    <div className="flex items-center gap-2 w-full rounded-full border border-gray-200 bg-white px-3 py-2 shadow-sm focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
      <button
        type="button"
        disabled={disabled}
        className="flex-shrink-0 p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Attach file"
      >
        <Plus size={18} />
      </button>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none disabled:cursor-not-allowed"
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!canSubmit}
        aria-label="Send message"
        className={`flex-shrink-0 p-1.5 rounded-full transition-colors ${
          canSubmit
            ? 'bg-blue-600 text-white hover:bg-blue-700'
            : 'bg-gray-100 text-gray-300 cursor-not-allowed'
        }`}
      >
        <ArrowUp size={16} />
      </button>
    </div>
  );
}
