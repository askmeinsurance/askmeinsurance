import type { ReactNode } from 'react';
import { PanelRightOpen } from 'lucide-react';
import { Sidebar } from '../sidebar/Sidebar';
import { ExcalidrawPanel } from '../canvas/ExcalidrawPanel';
import type { DiagramTab } from '../../types';

interface MainLayoutProps {
  sidebarCollapsed: boolean;
  onSidebarToggle: () => void;
  conversations?: { id: string; title: string; active?: boolean }[];
  onConversationSelect?: (id: string) => void;
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

  return (
    <div className="flex h-screen w-full overflow-hidden" style={{ backgroundColor: '#f8f9fa' }}>
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={onSidebarToggle}
        conversations={conversations}
        onConversationSelect={onConversationSelect}
        onNewChat={onNewChat}
        onSignOut={onSignOut}
        signedInEmail={signedInEmail}
      />
      <div className="relative flex flex-1 overflow-hidden">
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
