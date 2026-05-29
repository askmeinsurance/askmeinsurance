import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { DisclaimerCheckbox } from "../disclaimer/DisclaimerCheckbox";
import type { Message } from "../../types";

interface ChatPanelProps {
  messages: Message[];
  onSend: (text: string) => void | Promise<void>;
  hasDiagramPanel: boolean;
  isSending?: boolean;
  disclaimerAgreed: boolean;
  onDisclaimerCheckboxClick: () => void;
}

export function ChatPanel({ messages, onSend, hasDiagramPanel, isSending = false, disclaimerAgreed, onDisclaimerCheckboxClick }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const withCanvas = hasDiagramPanel;

  return (
    <div
      className={`flex flex-col h-full ${withCanvas ? "w-[40%] border-r border-gray-200" : "flex-1"}`}
    >
      <div className="flex-1 overflow-y-auto py-4">
        <div className={withCanvas ? "px-4" : "mx-auto w-full max-w-2xl px-4"}>
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div
        className={`flex-shrink-0 pb-4 pt-2 border-t border-gray-100 ${withCanvas ? "px-4" : "mx-auto w-full max-w-2xl px-4"}`}
      >
        <ChatInput onSubmit={onSend} disabled={isSending || !disclaimerAgreed} />
        <DisclaimerCheckbox agreed={disclaimerAgreed} onCheckboxClick={onDisclaimerCheckboxClick} />
      </div>
    </div>
  );
}
