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
    ? "bg-blue-50 text-blue-600"
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
  conversations = [],
  onConversationSelect,
  onConversationDelete,
  onNewChat,
  onSignOut,
  signedInEmail,
}: SidebarProps) {
  return (
    <aside
      className={`flex h-full flex-col border-r border-gray-200 bg-white transition-all duration-200 ${collapsed ? "w-14" : "w-64"}`}
    >
      <div
        className={`flex items-center border-b border-gray-100 px-3 py-3 ${collapsed ? "justify-center" : "gap-3"}`}
      >
        <IconButton label="Toggle sidebar" onClick={onToggle}>
          <Menu size={20} />
        </IconButton>
        {!collapsed && (
          <span className="truncate text-sm font-semibold text-gray-900">
            AskMeInsurance
          </span>
        )}
      </div>

      <div className={`px-3 py-3 ${collapsed ? "flex justify-center" : ""}`}>
        {collapsed ? (
          <IconButton label="New chat" variant="solid" size="md" onClick={onNewChat}>
            <Plus size={18} />
          </IconButton>
        ) : (
          <button
            type="button"
            onClick={onNewChat}
            className="flex w-full items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus size={16} />
            New chat
          </button>
        )}
      </div>

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
                        ? "bg-blue-50 text-blue-600"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-800"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onConversationSelect?.(item.id)}
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
                      className="rounded-md p-1 text-gray-400 opacity-0 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100"
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

      <div className="mt-auto border-t border-gray-100 px-2 py-3">
        {!collapsed && signedInEmail && (
          <p className="mb-2 truncate px-3 text-xs text-gray-400">Signed in as {signedInEmail}</p>
        )}
        {onSignOut && (
          <NavItem
            icon={<LogOut size={18} />}
            label="Sign out"
            collapsed={collapsed}
            onClick={onSignOut}
          />
        )}
      </div>
    </aside>
  );
}
