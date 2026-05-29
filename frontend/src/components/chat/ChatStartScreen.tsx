import { ChatInput } from "./ChatInput";

interface ChatStartScreenProps {
  onSubmit: (message: string) => void;
}

export function ChatStartScreen({ onSubmit }: ChatStartScreenProps) {
  return (
    <div
      className="flex flex-1 flex-col items-center justify-center h-full gap-6 px-4"
    >
      <div className="flex flex-col items-center gap-1 text-center">
        <p className="text-base text-gray-500">Welcome</p>
        <h1 className="text-3xl font-semibold text-gray-900">
          Where should we start?
        </h1>
      </div>

      <div className="w-full max-w-lg">
        <ChatInput onSubmit={onSubmit} placeholder="Ask InsureBot" />
      </div>
    </div>
  );
}
