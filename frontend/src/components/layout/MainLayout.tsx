import { type ReactNode, useEffect, useState } from 'react';
import { Menu, PanelRightOpen } from 'lucide-react';
import { Sidebar } from '../sidebar/Sidebar';
import { ExcalidrawPanel } from '../canvas/ExcalidrawPanel';
import type { DiagramTab } from '../../types';

interface MainLayoutProps {
  sidebarCollapsed: boolean;
  onSidebarToggle: () => void;
  conversations?: { id: string; title: string; active?: boolean }[];
  onConversationSelect?: (id: string) => void;
  onConversationDelete?: (id: string) => void;
  onNewChat?: () => void;
  onSignOut?: () => void;
  signedInEmail?: string;
  diagramTabs: DiagramTab[];
  activeDiagramTabId: string | null;
  isCanvasHidden: boolean;
  onDiagramTabSelect: (id: string) => void;
  onDiagramTabClose: (id: string) => void;
  onShowCanvas: () => void;
  onHideCanvas: () => void;
  onCloseAllDiagrams?: () => void;
  children: ReactNode;
}

export function MainLayout({
  sidebarCollapsed,
  onSidebarToggle,
  conversations,
  onConversationSelect,
  onConversationDelete,
  onNewChat,
  onSignOut,
  signedInEmail,
  diagramTabs,
  activeDiagramTabId,
  isCanvasHidden,
  onDiagramTabSelect,
  onDiagramTabClose,
  onShowCanvas,
  onHideCanvas,
  onCloseAllDiagrams,
  children,
}: MainLayoutProps) {
  const hasDiagrams = diagramTabs.length > 0;
  const shouldShowCanvasButton = hasDiagrams && isCanvasHidden;

  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      {isMobile && (
        <header className="fixed top-0 left-0 right-0 z-30 flex h-12 items-center gap-3 border-b border-gray-300/40 bg-transparent px-3">
          <button
            type="button"
            onClick={onSidebarToggle}
            aria-label="Toggle sidebar"
            className="rounded-md p-1.5 text-gray-600 hover:bg-gray-100"
          >
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold text-gray-400">AskMeInsurance</span>
        </header>
      )}
      {isMobile && !sidebarCollapsed && (
        <div
          className="fixed inset-0 z-40 bg-black/30"
          onClick={onSidebarToggle}
        />
      )}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={onSidebarToggle}
        mobile={isMobile}
        conversations={conversations}
        onConversationSelect={onConversationSelect}
        onConversationDelete={onConversationDelete}
        onNewChat={onNewChat}
        onSignOut={onSignOut}
        signedInEmail={signedInEmail}
      />
      <div className={`relative flex flex-1 overflow-hidden ${isMobile ? 'pt-12' : ''}`}>
        {children}
        {shouldShowCanvasButton && (
          <button
            type="button"
            onClick={onShowCanvas}
            className="absolute right-4 top-4 z-10 inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
          >
            <PanelRightOpen size={14} />
            Show canvas
          </button>
        )}
        <ExcalidrawPanel
          visible={!isCanvasHidden}
          tabs={diagramTabs}
          activeTabId={activeDiagramTabId}
          onTabSelect={onDiagramTabSelect}
          onTabClose={onDiagramTabClose}
          onHide={onHideCanvas}
          onCloseAll={onCloseAllDiagrams}
        />
      </div>
    </div>
  );
}
