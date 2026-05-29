import { useEffect, useMemo, useRef } from 'react';
import { Excalidraw } from '@excalidraw/excalidraw';
import '@excalidraw/excalidraw/index.css';
import { FileText, X } from 'lucide-react';
import type { DiagramTab } from '../../types';
import type { ExcalidrawImperativeAPI } from '@excalidraw/excalidraw/types';

interface ExcalidrawPanelProps {
  visible: boolean;
  tabs: DiagramTab[];
  activeTabId: string | null;
  onTabSelect: (id: string) => void;
  onTabClose: (id: string) => void;
  onHide?: () => void;
  onCloseAll?: () => void;
}

export function ExcalidrawPanel({
  visible,
  tabs,
  activeTabId,
  onTabSelect,
  onTabClose,
  onHide,
  onCloseAll,
}: ExcalidrawPanelProps) {
  const excalidrawApiRef = useRef<ExcalidrawImperativeAPI | null>(null);

  const activeTab = useMemo(
    () => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0],
    [activeTabId, tabs]
  );

  useEffect(() => {
    if (!visible || !activeTab) return;

    const rafId = window.requestAnimationFrame(() => {
      const api = excalidrawApiRef.current;
      if (!api) return;
      const elements = api.getSceneElements();
      if (!elements.length) return;
      api.scrollToContent(elements, {
        fitToViewport: true,
        viewportZoomFactor: 1,
        animate: false,
      });
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [activeTab?.id, visible]);

  if (!visible || !tabs.length || !activeTab) return null;

  return (
    <aside className="hidden md:flex h-full flex-1 flex-col border-l border-slate-200 bg-[#f6f8fb]">
      <div className="shrink-0 border-b border-slate-200 bg-white/95 px-3 py-2 backdrop-blur">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-slate-700">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-900 text-white">
              <FileText size={13} />
            </div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em]">Diagrams</p>
          </div>
          <div className="flex items-center gap-1">
            {onHide && (
              <button
                type="button"
                onClick={onHide}
                className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
              >
                Hide
              </button>
            )}
            {onCloseAll && (
              <button
                type="button"
                onClick={onCloseAll}
                className="rounded-md px-2 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
              >
                Close all
              </button>
            )}
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {tabs.map((tab, index) => {
            const isActive = tab.id === activeTab.id;
            return (
              <div
                key={tab.id}
                className={`group flex min-w-[170px] items-center gap-2 rounded-lg border px-3 py-2 text-left transition-all ${
                  isActive
                    ? 'border-slate-900 bg-slate-900 text-white shadow-sm'
                    : 'border-slate-200 bg-white text-slate-700 hover:-translate-y-0.5 hover:border-slate-300'
                }`}
              >
                <button type="button" onClick={() => onTabSelect(tab.id)} className="truncate text-xs font-medium">
                  {index + 1}. {tab.title}
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onTabClose(tab.id);
                  }}
                  className={`ml-auto rounded p-0.5 ${isActive ? 'hover:bg-white/20' : 'hover:bg-slate-100'}`}
                >
                  <X size={13} />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        <Excalidraw
          key={activeTab.id}
          excalidrawAPI={(api) => {
            excalidrawApiRef.current = api;
          }}
          viewModeEnabled
          zenModeEnabled
          UIOptions={{
            canvasActions: {
              changeViewBackgroundColor: false,
              clearCanvas: false,
              export: false,
              loadScene: false,
              saveAsImage: false,
              saveToActiveFile: false,
              toggleTheme: false,
            },
            tools: {
              image: false,
            },
          }}
          initialData={{
            elements: activeTab.diagram.elements as never,
            appState: activeTab.diagram.appState as never,
            files: activeTab.diagram.files as never,
            scrollToContent: true,
          }}
        />
      </div>
    </aside>
  );
}
