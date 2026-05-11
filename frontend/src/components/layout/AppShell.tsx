import { useState, type ReactNode } from 'react';
import { Sidebar } from '../sidebar/Sidebar';

interface AppShellProps {
  children?: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  function handleSidebarToggle() {
    setSidebarCollapsed((prev) => !prev);
  }

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ backgroundColor: '#f8f9fa' }}>
      <Sidebar collapsed={sidebarCollapsed} onToggle={handleSidebarToggle} />
      <main className="flex flex-1 flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}
