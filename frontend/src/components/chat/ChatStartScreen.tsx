import { ChatInput } from "./ChatInput";
import { DisclaimerCheckbox } from "../disclaimer/DisclaimerCheckbox";

interface ChatStartScreenProps {
  onSubmit: (message: string) => void;
  disclaimerAgreed: boolean;
  onDisclaimerCheckboxClick: () => void;
}

export function ChatStartScreen({ onSubmit, disclaimerAgreed, onDisclaimerCheckboxClick }: ChatStartScreenProps) {
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
        <ChatInput onSubmit={onSubmit} placeholder="Ask InsureBot" disabled={!disclaimerAgreed} />
        <DisclaimerCheckbox agreed={disclaimerAgreed} onCheckboxClick={onDisclaimerCheckboxClick} />
      </div>
    </div>
  );
}
