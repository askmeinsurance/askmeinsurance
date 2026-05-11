import {
  Menu,
  Plus,
  MessageSquare,
  Bookmark,
  Settings,
  HelpCircle,
  ChevronRight,
} from "lucide-react";
import { IconButton } from "../ui/IconButton";

interface ChatHistoryItem {
  id: string;
  title: string;
  active?: boolean;
}

const MOCK_HISTORY: ChatHistoryItem[] = [
  { id: "1", title: "Understanding life insurance", active: true },
  { id: "2", title: "Term vs whole life policy" },
  { id: "3", title: "Critical illness coverage" },
  { id: "4", title: "Medishield Life top-ups" },
];

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  collapsed: boolean;
  active?: boolean;
}

function NavItem({ icon, label, collapsed, active = false }: NavItemProps) {
  const activeClass = active
    ? "bg-blue-50 text-blue-600"
    : "text-gray-600 hover:bg-gray-100 hover:text-gray-800";

  return (
    <button
      type="button"
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
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={`flex h-full flex-col border-r border-gray-200 bg-white transition-all duration-200 ${collapsed ? "w-14" : "w-64"}`}
    >
      {/* Header */}
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

      {/* New Chat */}
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

      {/* Nav */}
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

      {/* Chat History */}
      {!collapsed && (
        <div className="mt-4 flex flex-1 flex-col overflow-hidden px-2">
          <div className="mb-1 flex items-center justify-between px-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Chats
            </span>
            <ChevronRight size={14} className="text-gray-400" />
          </div>
          <ul className="flex flex-col gap-0.5 overflow-y-auto">
            {MOCK_HISTORY.map((item) => (
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
        </div>
      )}

      {/* Footer */}
      <div className="mt-auto border-t border-gray-100 px-2 py-3">
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
