import { useState, useEffect } from "react";
import { Bot } from "lucide-react";

const THINKING_MESSAGES = [
  "Reading through the policies...",
  "Checking the fine print...",
  "Consulting the coverage rules...",
  "Comparing your options...",
  "Calculating eligibility...",
  "Searching the knowledge base...",
];

export function ThinkingIndicator() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(
      () => setIndex((i) => (i + 1) % THINKING_MESSAGES.length),
      2500
    );
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex gap-3 mb-4">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-accent flex items-center justify-center mt-0.5">
        <Bot size={15} className="text-white" />
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-1.5 pt-1">
        <div className="flex items-center gap-1">
          <span
            className="inline-block w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="inline-block w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="inline-block w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
            style={{ animationDelay: "300ms" }}
          />
        </div>
        <span className="text-xs text-gray-400">{THINKING_MESSAGES[index]}</span>
      </div>
    </div>
  );
}
