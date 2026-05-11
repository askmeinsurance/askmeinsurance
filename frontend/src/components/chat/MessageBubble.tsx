import { Bot } from 'lucide-react';
import { ThinkingSection } from './ThinkingSection';
import type { Message } from '../../types';

interface MessageBubbleProps {
  message: Message;
}

function formatContent(text: string) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let key = 0;

  function flushList() {
    if (listItems.length > 0) {
      elements.push(
        <ul key={key++} className="list-disc list-inside my-1 space-y-0.5">
          {listItems.map((item, i) => (
            <li key={i} className="text-sm text-gray-800">
              {renderInline(item)}
            </li>
          ))}
        </ul>
      );
      listItems = [];
    }
  }

  function renderInline(raw: string): React.ReactNode {
    const parts = raw.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <span key={i} className="font-medium">{part.slice(2, -2)}</span>;
      }
      return part;
    });
  }

  for (const line of lines) {
    if (line.startsWith('- ') || line.startsWith('* ')) {
      listItems.push(line.slice(2));
      continue;
    }

    flushList();

    if (!line.trim()) {
      elements.push(<div key={key++} className="h-2" />);
    } else if (line.startsWith('### ')) {
      elements.push(
        <p key={key++} className="text-sm font-semibold text-gray-900 mt-2">
          {renderInline(line.slice(4))}
        </p>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <p key={key++} className="text-sm font-semibold text-gray-900 mt-2">
          {renderInline(line.slice(3))}
        </p>
      );
    } else if (line.startsWith('# ')) {
      elements.push(
        <p key={key++} className="text-sm font-semibold text-gray-900 mt-2">
          {renderInline(line.slice(2))}
        </p>
      );
    } else {
      elements.push(
        <p key={key++} className="text-sm text-gray-800 leading-relaxed">
          {renderInline(line)}
        </p>
      );
    }
  }

  flushList();
  return elements;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[70%] bg-gray-100 rounded-2xl px-4 py-2">
          <p className="text-sm text-gray-900">{message.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 mb-4">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center mt-0.5">
        <Bot size={15} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        {message.thinking && <ThinkingSection content={message.thinking} />}
        <div>{formatContent(message.content)}</div>
      </div>
    </div>
  );
}
