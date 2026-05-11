import { useEffect, useState } from 'react';
import { MainLayout } from './components/layout/MainLayout';
import { ChatStartScreen } from './components/chat/ChatStartScreen';
import { ChatPanel } from './components/chat/ChatPanel';
import { PaginatedFormModal } from './components/forms/PaginatedFormModal';
import { textOnlyMessages, canvasMessages } from './mocks/messages';
import type { AppView, DiagramPayload, DiagramTab, FormAnswerMap, FormRequest, Message } from './types';
import type { AuthSession } from './types/auth';
import configuredFormRequest from './config/llm-form-request.json';
import { clearAuthSession, readAuthSession } from './lib/auth';
import { streamChatMessage, submitFormAnswers } from './lib/chatApi';
import './index.css';

const DEFAULT_DIAGRAM_FILE = '/financial_planning_diagram.excalidraw';
const DEFAULT_DIAGRAM_TITLE = 'Financial Planning Diagram';

function makeTabId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createDemoFormRequest(): FormRequest {
  return {
    id: `insurance-intake-${Date.now()}`,
    title: 'Insurance Planning Intake',
    description: 'Answer these short questions so I can tailor the recommendation.',
    submitLabel: 'Submit Details',
    pages: [
      {
        id: 'profile',
        title: 'Profile Basics',
        description: 'Tell me who this plan is for.',
        fields: [
          { id: 'fullName', type: 'text', label: 'Full Name', required: true, placeholder: 'e.g. Alex Tan' },
          { id: 'age', type: 'text', label: 'Age', required: true, placeholder: 'e.g. 35' },
          {
            id: 'smoker',
            type: 'radio',
            label: 'Smoking Status',
            required: true,
            options: [
              { label: 'Non-smoker', value: 'non-smoker' },
              { label: 'Smoker', value: 'smoker' },
            ],
          },
        ],
      },
      {
        id: 'coverage',
        title: 'Coverage Preference',
        description: 'Set the initial plan preference.',
        fields: [
          {
            id: 'goal',
            type: 'select',
            label: 'Primary Goal',
            required: true,
            options: [
              { label: 'Income protection', value: 'income' },
              { label: 'Legacy planning', value: 'legacy' },
              { label: 'Hospitalization buffer', value: 'medical' },
            ],
          },
          {
            id: 'notes',
            type: 'textarea',
            label: 'Anything else I should consider?',
            placeholder: 'Optional context...',
          },
          {
            id: 'consent',
            type: 'checkbox',
            label: 'I confirm this information is accurate.',
            required: true,
          },
        ],
      },
    ],
  };
}

function getConfiguredFormRequest(): FormRequest {
  const config = configuredFormRequest as Partial<FormRequest>;
  if (!config || !config.id || !config.title || !Array.isArray(config.pages) || !config.pages.length) {
    return createDemoFormRequest();
  }
  return config as FormRequest;
}

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [view, setView] = useState<AppView>('start');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [diagramState, setDiagramState] = useState({ tabs: [] as DiagramTab[], activeTabId: null as string | null });
  const [isCanvasHidden, setIsCanvasHidden] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeFormRequest, setActiveFormRequest] = useState<FormRequest | null>(null);
  const { tabs: diagramTabs, activeTabId: activeDiagramTabId } = diagramState;
  const hasVisibleCanvas = diagramTabs.length > 0 && !isCanvasHidden;

  useEffect(() => {
    const persistedSession = readAuthSession();
    setSession(persistedSession);
  }, []);

  function handleSignOut() {
    clearAuthSession();
    setSession(null);
    setMessages([]);
    setView('start');
    setActiveFormRequest(null);
  }

  function handleUnauthorized() {
    handleSignOut();
  }

  async function openDiagramFromPublicFile() {
    try {
      const response = await fetch(DEFAULT_DIAGRAM_FILE);
      if (!response.ok) return;
      const parsed = (await response.json()) as DiagramPayload;
      if (!Array.isArray(parsed?.elements)) return;

      const now = Date.now();
      const tabId = makeTabId();
      setDiagramState({
        tabs: [
          {
            id: tabId,
            title: DEFAULT_DIAGRAM_TITLE,
            createdAt: now,
            updatedAt: now,
            diagram: {
              elements: parsed.elements,
              appState: parsed.appState,
              files: parsed.files,
            },
          },
        ],
        activeTabId: tabId,
      });
      setIsCanvasHidden(false);
      setSidebarCollapsed(true);
    } catch {
      // Intentionally no-op: app should still work without the default diagram file.
    }
  }

  function saveDiagramState(nextTabs: DiagramTab[], nextActiveTabId: string | null) {
    setDiagramState({ tabs: nextTabs, activeTabId: nextActiveTabId });
  }

  function appendDiagramTabs(entries: Array<{ title?: string; data: DiagramPayload }>) {
    if (!entries.length) return;

    const now = Date.now();
    const nextTabs = [...diagramTabs];
    let activeId: string | null = activeDiagramTabId;
    entries.forEach((entry) => {
      const newTab: DiagramTab = {
        id: makeTabId(),
        title: entry.title || `Diagram ${nextTabs.length + 1}`,
        createdAt: now,
        updatedAt: now,
        diagram: entry.data,
      };
      nextTabs.push(newTab);
      activeId = newTab.id;
    });
    saveDiagramState(nextTabs, activeId);
  }

  function applyBotDiagrams(nextMessages: Message[]) {
    const botMessages = nextMessages.filter((message) => message.role === 'bot');
    const diagramMessages = botMessages.filter((message) => message.hasDiagram && message.diagramData);

    if (diagramMessages.length) {
      appendDiagramTabs(
        diagramMessages.map((message) => ({
          title: message.diagramTitle,
          data: message.diagramData as DiagramPayload,
        }))
      );
      setIsCanvasHidden(false);
      setSidebarCollapsed(true);
    }

    const latestFormRequest = [...botMessages]
      .reverse()
      .find((message) => message.formRequest)?.formRequest;
    if (latestFormRequest) {
      setActiveFormRequest(latestFormRequest);
    }
  }

  function handleSubmit(message: string) {
    const isCanvasRequest = message.toLowerCase().includes('canvas') ||
      message.toLowerCase().includes('illustrate') ||
      message.toLowerCase().includes('visuali');
    const isFormRequest = message.toLowerCase().includes('form');

    const nextMessages = isCanvasRequest
      ? canvasMessages
      : isFormRequest
        ? [
            {
              id: '1',
              role: 'user' as const,
              content: message,
            },
            {
              id: '2',
              role: 'bot' as const,
              content: 'I need a few details from you before I proceed. Please complete the form.',
              formRequest: getConfiguredFormRequest(),
            },
          ]
        : textOnlyMessages;
    setMessages(nextMessages);
    applyBotDiagrams(nextMessages);
    setView('chat');
    if (isCanvasRequest) {
      void openDiagramFromPublicFile();
    }
  }

  async function handleSend(text: string) {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    };

    const isCanvasRequest = text.toLowerCase().includes('canvas') ||
      text.toLowerCase().includes('illustrate') ||
      text.toLowerCase().includes('visuali');
    const isFormRequest = text.toLowerCase().includes('form');

    if (isCanvasRequest) {
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: canvasMessages[1].content,
      };
      setMessages((prev) => [...prev, userMessage, botMessage]);
      void openDiagramFromPublicFile();
      return;
    }

    if (isFormRequest) {
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: 'I need a few details from you before I proceed. Please complete the form.',
        formRequest: getConfiguredFormRequest(),
      };
      setMessages((prev) => {
        const next = [...prev, userMessage, botMessage];
        applyBotDiagrams(next);
        return next;
      });
      return;
    }

    setMessages((prev) => [...prev, userMessage]);

    if (!session) {
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: textOnlyMessages[1]?.content || 'How can I help with your insurance planning today?',
        },
      ]);
      return;
    }

    setIsSending(true);

    try {
      const result = await streamChatMessage({
        message: text,
        accessToken: session.accessToken,
      });
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: result.text,
        formRequest: result.formRequest,
      };

      setMessages((prev) => {
        const next = [...prev, botMessage];
        applyBotDiagrams(next);
        return next;
      });
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 401) {
        handleUnauthorized();
        return;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: 'I hit a connection issue while contacting the backend. Please try again.',
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleFormClose() {
    setActiveFormRequest(null);
  }

  function handleFormSubmit(formId: string, answers: FormAnswerMap) {
    if (!session) {
      const fallbackKey = 'form_submissions_fallback';
      const raw = window.localStorage.getItem(fallbackKey);
      const existing = raw ? (JSON.parse(raw) as Array<{ formId: string; answers: FormAnswerMap; submittedAt: string }>) : [];
      existing.push({ formId, answers, submittedAt: new Date().toISOString() });
      window.localStorage.setItem(fallbackKey, JSON.stringify(existing));
      setActiveFormRequest(null);
      return;
    }

    submitFormAnswers({
      formId,
      answers,
      accessToken: session.accessToken,
    })
      .catch((error) => {
        const status = (error as { status?: number }).status;
        if (status === 401) {
          handleUnauthorized();
          return;
        }

        const fallbackKey = 'form_submissions_fallback';
        const raw = window.localStorage.getItem(fallbackKey);
        const existing = raw ? (JSON.parse(raw) as Array<{ formId: string; answers: FormAnswerMap; submittedAt: string }>) : [];
        existing.push({ formId, answers, submittedAt: new Date().toISOString() });
        window.localStorage.setItem(fallbackKey, JSON.stringify(existing));
      });
    setActiveFormRequest(null);
  }

  function handleDiagramTabSelect(id: string) {
    saveDiagramState(diagramTabs, id);
  }

  function handleDiagramTabClose(id: string) {
    const nextTabs = diagramTabs.filter((tab) => tab.id !== id);
    const nextActiveTabId =
      activeDiagramTabId === id ? nextTabs[nextTabs.length - 1]?.id ?? null : activeDiagramTabId;
    saveDiagramState(nextTabs, nextActiveTabId);
    if (!nextTabs.length) {
      setIsCanvasHidden(false);
      setSidebarCollapsed(false);
    }
  }

  function handleCloseAllDiagrams() {
    saveDiagramState([], null);
    setIsCanvasHidden(false);
    setSidebarCollapsed(false);
  }

  function handleSidebarToggle() {
    setSidebarCollapsed((prev) => !prev);
  }

  function handleHideCanvas() {
    setIsCanvasHidden(true);
  }

  function handleShowCanvas() {
    setIsCanvasHidden(false);
  }

  // Auth gate temporarily disabled.

  return (
    <MainLayout
      sidebarCollapsed={sidebarCollapsed}
      onSidebarToggle={handleSidebarToggle}
      onSignOut={handleSignOut}
      signedInEmail={session?.email}
      diagramTabs={diagramTabs}
      activeDiagramTabId={activeDiagramTabId}
      isCanvasHidden={isCanvasHidden}
      onDiagramTabSelect={handleDiagramTabSelect}
      onDiagramTabClose={handleDiagramTabClose}
      onShowCanvas={handleShowCanvas}
      onHideCanvas={handleHideCanvas}
      onCloseAllDiagrams={handleCloseAllDiagrams}
    >
      {view === 'start' && <ChatStartScreen onSubmit={handleSubmit} />}
      {view === 'chat' && (
        <ChatPanel messages={messages} onSend={handleSend} hasDiagramPanel={hasVisibleCanvas} isSending={isSending} />
      )}
      <PaginatedFormModal
        key={activeFormRequest?.id ?? 'no-form'}
        isOpen={Boolean(activeFormRequest)}
        request={activeFormRequest}
        onClose={handleFormClose}
        onSubmit={handleFormSubmit}
      />
    </MainLayout>
  );
}
