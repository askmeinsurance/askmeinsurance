import { useEffect, useRef } from "react";
import { Wrench, Zap } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import type { Message } from "../../types";

interface ChatPanelProps {
  messages: Message[];
  onSend: (text: string) => void;
  hasDiagramPanel: boolean;
}

export function ChatPanel({ messages, onSend, hasDiagramPanel }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const withCanvas = hasDiagramPanel;

  return (
    <div
      className={`flex flex-col h-full ${withCanvas ? "w-[40%] border-r border-gray-200" : "flex-1"}`}
    >
      {/* Scrollable messages */}
      <div className="flex-1 overflow-y-auto py-4">
        <div className={withCanvas ? "px-4" : "mx-auto w-full max-w-2xl px-4"}>
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Pinned input area */}
      <div
        className={`flex-shrink-0 pb-4 pt-2 border-t border-gray-100 ${withCanvas ? "px-4" : "mx-auto w-full max-w-2xl px-4"}`}
      >
        <div className="flex items-center gap-2 mb-2">
          <button
            type="button"
            className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-100 hover:bg-gray-200 rounded-full px-3 py-1 transition-colors"
          >
            <Wrench size={12} />
            <span>Tools</span>
          </button>
          <div className="flex items-center gap-1 text-xs text-gray-400 ml-auto">
            <Zap size={12} className="text-yellow-500" />
            <span>Fast</span>
          </div>
        </div>
        <ChatInput onSubmit={onSend} />
      </div>
    </div>
  );
}
