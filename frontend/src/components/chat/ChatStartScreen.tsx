import { Image, Music, GraduationCap, PenLine, Sun, Video } from "lucide-react";
import { ChatInput } from "./ChatInput";

interface QuickAction {
  label: string;
  icon: React.ReactNode;
}

const ROW_ONE: QuickAction[] = [
  { label: "Create image", icon: <Image size={15} /> },
  { label: "Create music", icon: <Music size={15} /> },
  { label: "Help me learn", icon: <GraduationCap size={15} /> },
  { label: "Write anything", icon: <PenLine size={15} /> },
];

const ROW_TWO: QuickAction[] = [
  { label: "Boost my day", icon: <Sun size={15} /> },
  { label: "Create a video", icon: <Video size={15} /> },
];

interface ChatStartScreenProps {
  onSubmit: (message: string) => void;
}

export function ChatStartScreen({ onSubmit }: ChatStartScreenProps) {
  return (
    <div
      className="flex flex-1 flex-col items-center justify-center h-full gap-6 px-4"
      style={{ backgroundColor: "#f8f9fa" }}
    >
      <div className="flex flex-col items-center gap-1 text-center">
        <p className="text-base text-gray-500">✦ Hi KuanFei</p>
        <h1 className="text-3xl font-semibold text-gray-900">
          Where should we start?
        </h1>
      </div>

      <div className="w-full max-w-lg">
        <ChatInput onSubmit={onSubmit} placeholder="Ask InsureBot" />
      </div>

      <div className="flex flex-col items-center gap-2">
        <div className="flex flex-wrap justify-center gap-2">
          {ROW_ONE.map((action) => (
            <QuickActionButton
              key={action.label}
              action={action}
              onSubmit={onSubmit}
            />
          ))}
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          {ROW_TWO.map((action) => (
            <QuickActionButton
              key={action.label}
              action={action}
              onSubmit={onSubmit}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

interface QuickActionButtonProps {
  action: QuickAction;
  onSubmit: (message: string) => void;
}

function QuickActionButton({ action, onSubmit }: QuickActionButtonProps) {
  return (
    <button
      type="button"
      onClick={() => onSubmit(action.label)}
      className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors shadow-sm"
    >
      <span className="text-gray-500">{action.icon}</span>
      {action.label}
    </button>
  );
}
