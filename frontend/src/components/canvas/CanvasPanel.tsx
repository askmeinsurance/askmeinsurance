import { Code, Eye, Share2, X, RotateCcw, Maximize2 } from 'lucide-react';

interface CanvasPanelProps {
  visible: boolean;
  onClose?: () => void;
}

function SystemPromptCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-pale text-accent">
          <span className="text-xs font-bold">S</span>
        </div>
        <span className="text-sm font-semibold text-gray-800">System Prompt</span>
      </div>
      <blockquote className="mb-3 rounded-lg bg-gray-50 p-3 text-xs italic text-gray-600 leading-relaxed">
        "You are a professional Financial Advisor. Always maintain a conservative, risk-averse tone.
        Use formal language. Ensure all advice includes a legal disclaimer."
      </blockquote>
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>Permanent Context</span>
        <span>34 tokens</span>
      </div>
    </div>
  );
}

function SkillItem({ color, label, trigger }: { color: string; label: string; trigger: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-gray-100 bg-white p-3">
      <div className={`mt-0.5 h-4 w-4 shrink-0 rounded-full ${color}`} />
      <div className="min-w-0">
        <p className="text-xs font-semibold text-gray-800">{label}</p>
        <p className="text-xs text-gray-400 truncate">{trigger}</p>
      </div>
      <span className="ml-auto shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
        120 tokens
      </span>
    </div>
  );
}

function AvailableSkillsCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-green-100 text-green-600">
          <span className="text-xs font-bold">A</span>
        </div>
        <span className="text-sm font-semibold text-gray-800">Available Skills</span>
      </div>
      <div className="flex flex-col gap-2">
        <SkillItem
          color="bg-yellow-400"
          label="Crypto Analysis Skill"
          trigger="Trigger: bitcoin, ethereum, crypto"
        />
        <SkillItem
          color="bg-accent-muted"
          label="Tax Optimisation Skill"
          trigger="Trigger: tax, deduction, ira"
        />
      </div>
      <p className="mt-3 text-xs text-gray-400">
        *Skills are only loaded into the "Brain" when the user asks something relevant.
      </p>
    </div>
  );
}

function AgentBrainFooter() {
  return (
    <div className="rounded-xl bg-gray-900 p-4 text-white">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-bold">
            G
          </div>
          <div>
            <p className="text-xs font-semibold">The Agent's "Brain"</p>
            <p className="text-xs text-gray-400">Active Context Monitor</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-lg font-bold text-accent-muted">43%</p>
          <p className="text-xs text-gray-400">TOTAL ACTIVE TOKENS</p>
        </div>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-700">
        <div className="h-full w-[43%] rounded-full bg-accent-ring" />
      </div>
      <div className="mt-1 flex justify-between text-xs text-gray-400">
        <span>SYSTEM LAYER</span>
        <span>TOKEN USAGE REMAINING</span>
      </div>
    </div>
  );
}

export function CanvasPanel({ visible, onClose }: CanvasPanelProps) {
  if (!visible) return null;

  return (
    <div className="flex h-full flex-1 flex-col border-l border-gray-200 bg-white">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b border-gray-200 px-4 py-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent-pale">
            <span className="text-xs font-bold text-accent">A</span>
          </div>
          <span className="truncate text-sm text-gray-600">Agent Architecture Visualiser</span>
          <div className="flex items-center gap-1 text-gray-400">
            <button type="button" className="rounded p-1 hover:bg-gray-100">
              <RotateCcw size={14} />
            </button>
            <button type="button" className="rounded p-1 hover:bg-gray-100">
              <Maximize2 size={14} />
            </button>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="flex items-center gap-1">
              <Code size={12} />
              Code
            </span>
          </button>
          <button
            type="button"
            className="rounded-lg border border-accent-light bg-accent-pale px-3 py-1 text-xs font-medium text-accent hover:bg-accent-light transition-colors"
          >
            <span className="flex items-center gap-1">
              <Eye size={12} />
              Preview
            </span>
          </button>
          <button
            type="button"
            className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <span className="flex items-center gap-1">
              <Share2 size={12} />
              Share
            </span>
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="ml-1 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-xl">
          <h1 className="mb-1 text-center text-2xl font-bold text-gray-900">
            Agent Skill vs. System Prompt
          </h1>
          <p className="mb-6 text-center text-sm text-gray-500">
            Visualising the "Agentic Stack" and Context Efficiency
          </p>
          <div className="flex flex-col gap-4">
            <SystemPromptCard />
            <AvailableSkillsCard />
            <AgentBrainFooter />
          </div>
        </div>
      </div>
    </div>
  );
}
