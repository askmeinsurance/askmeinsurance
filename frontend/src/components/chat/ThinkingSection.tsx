import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface ThinkingSectionProps {
  content: string;
}

export function ThinkingSection({ content }: ThinkingSectionProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
      >
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        <span>{expanded ? 'Hide thinking' : 'Show thinking'}</span>
      </button>
      {expanded && (
        <div className="mt-1 pl-3 border-l-2 border-accent-light text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      )}
    </div>
  );
}
