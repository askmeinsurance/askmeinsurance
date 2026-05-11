import {
  Menu,
  Plus,
  MessageSquare,
  Bookmark,
  Settings,
  HelpCircle,
  ChevronRight,
  LogOut,
} from "lucide-react";
import type { ReactNode } from "react";
import { IconButton } from "../ui/IconButton";

interface ChatHistoryItem {
  id: string;
  title: string;
  active?: boolean;
}

const CHAT_HISTORY: ChatHistoryItem[] = [];

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
  onSignOut?: () => void;
  signedInEmail?: string;
}

export function Sidebar({ collapsed, onToggle, onSignOut, signedInEmail }: SidebarProps) {
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
            InsureBot SG
          </span>
        )}
      </div>

      <div className={`px-3 py-3 ${collapsed ? "flex justify-center" : ""}`}>
        {collapsed ? (
          <IconButton label="New chat" variant="solid" size="md">
            <Plus size={18} />
          </IconButton>
        ) : (
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus size={16} />
            New chat
          </button>
        )}
      </div>

      <nav className="flex flex-col gap-1 px-2">
        <NavItem
          icon={<MessageSquare size={18} />}
          label="My stuff"
          collapsed={collapsed}
        />
        <NavItem
          icon={<Bookmark size={18} />}
          label="Saved"
          collapsed={collapsed}
        />
      </nav>

      {!collapsed && (
        <div className="mt-4 flex flex-1 flex-col overflow-hidden px-2">
          <div className="mb-1 flex items-center justify-between px-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Chats
            </span>
            <ChevronRight size={14} className="text-gray-400" />
          </div>
          {CHAT_HISTORY.length === 0 ? (
            <p className="px-2 py-2 text-sm text-gray-500">No conversations yet.</p>
          ) : (
            <ul className="flex flex-col gap-0.5 overflow-y-auto">
              {CHAT_HISTORY.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-sm transition-colors ${
                      item.active
                        ? "bg-blue-50 text-blue-600"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-800"
                    }`}
                  >
                    <MessageSquare size={14} className="shrink-0" />
                    <span className="truncate">{item.title}</span>
                  </button>
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
        <NavItem
          icon={<Settings size={18} />}
          label="Settings"
          collapsed={collapsed}
        />
        <NavItem
          icon={<HelpCircle size={18} />}
          label="Help"
          collapsed={collapsed}
        />
      </div>
    </aside>
  );
}
