import {
  Menu,
  Plus,
  MessageSquare,
  ChevronRight,
  LogOut,
  Trash2,
} from "lucide-react";
import type { ReactNode } from "react";
import { IconButton } from "../ui/IconButton";

interface ChatHistoryItem {
  id: string;
  title: string;
  active?: boolean;
}

interface NavItemProps {
  icon: ReactNode;
  label: string;
  collapsed: boolean;
  active?: boolean;
  onClick?: () => void;
}

function NavItem({ icon, label, collapsed, active = false, onClick }: NavItemProps) {
  const activeClass = active
    ? "bg-neutral-100 text-neutral-900"
    : "text-gray-600 hover:bg-gray-100 hover:text-gray-800";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${activeClass} ${collapsed ? "justify-center" : ""}`}
    >
      <span className="shrink-0">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobile?: boolean;
  conversations?: ChatHistoryItem[];
  onConversationSelect?: (id: string) => void;
  onConversationDelete?: (id: string) => void;
  onNewChat?: () => void;
  onSignOut?: () => void;
  signedInEmail?: string;
}

export function Sidebar({
  collapsed,
  onToggle,
  mobile = false,
  conversations = [],
  onConversationSelect,
  onConversationDelete,
  onNewChat,
  onSignOut,
  signedInEmail,
}: SidebarProps) {
  const closeSidebar = () => { if (mobile && !collapsed) onToggle(); };

  const positionClass = mobile
    ? !collapsed
      ? 'fixed inset-y-0 left-0 z-50 w-64 shadow-xl'
      : 'w-0 overflow-hidden'
    : collapsed
      ? 'w-14'
      : 'w-64';

  return (
    <aside
      className={`flex h-full flex-col border-r border-gray-200 bg-white transition-all duration-200 ${positionClass}`}
    >
      <div
        className={`flex items-center border-b border-gray-100 px-3 py-3 ${collapsed ? "justify-center" : "gap-3"}`}
      >
        <IconButton label="Toggle sidebar" onClick={onToggle}>
          <Menu size={20} />
        </IconButton>
        {!collapsed && (
          <>
            <span className="truncate text-sm font-semibold text-gray-900">
              AskMeInsurance
            </span>
            <div className="ml-auto flex items-center gap-0.5">
              <a
                href="https://github.com/askmeinsurance/askmeinsurance"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View on GitHub"
                className="shrink-0 rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
                </svg>
              </a>
              <a
                href="https://www.linkedin.com/in/joelkuanfeilee"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View on LinkedIn"
                className="shrink-0 rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                </svg>
              </a>
            </div>
          </>
        )}
      </div>

      {!(mobile && collapsed) && (
        <div className={`px-3 py-3 ${collapsed ? "flex justify-center" : ""}`}>
          {collapsed ? (
            <IconButton label="New chat" variant="solid" size="md" onClick={onNewChat}>
              <Plus size={18} />
            </IconButton>
          ) : (
            <button
              type="button"
              onClick={() => { onNewChat?.(); closeSidebar(); }}
              className="flex w-full items-center gap-2 rounded-lg bg-neutral-900 px-3 py-2 text-sm font-medium text-white hover:bg-neutral-800 transition-colors"
            >
              <Plus size={16} />
              New chat
            </button>
          )}
        </div>
      )}

      {!collapsed && (
        <div className="mt-4 flex flex-1 flex-col overflow-hidden px-2">
          <div className="mb-1 flex items-center justify-between px-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Chats
            </span>
            <ChevronRight size={14} className="text-gray-400" />
          </div>
          {conversations.length === 0 ? (
            <p className="px-2 py-2 text-sm text-gray-500">No conversations yet.</p>
          ) : (
            <ul className="flex flex-col gap-0.5 overflow-y-auto">
              {conversations.map((item) => (
                <li key={item.id}>
                  <div
                    className={`group flex w-full items-center gap-1 rounded-lg px-1 py-0.5 text-sm transition-colors ${
                      item.active
                        ? "bg-neutral-100 text-neutral-900"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-800"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => { onConversationSelect?.(item.id); closeSidebar(); }}
                      className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1 py-1"
                    >
                      <MessageSquare size={14} className="shrink-0" />
                      <span className="truncate">{item.title}</span>
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete conversation ${item.title}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onConversationDelete?.(item.id);
                      }}
                      className="rounded-md p-1 text-gray-300 transition hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {!(mobile && collapsed) && (
        <div className="mt-auto border-t border-gray-100 px-2 py-3">
          {!collapsed && signedInEmail && (
            <p className="mb-2 truncate px-3 text-xs text-gray-400">Signed in as {signedInEmail}</p>
          )}
          {onSignOut && (
            <NavItem
              icon={<LogOut size={18} />}
              label="Sign out"
              collapsed={collapsed}
              onClick={() => { onSignOut(); closeSidebar(); }}
            />
          )}
        </div>
      )}
    </aside>
  );
}
