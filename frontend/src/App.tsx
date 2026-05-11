import { useEffect, useState } from 'react';
import { MainLayout } from './components/layout/MainLayout';
import { ChatStartScreen } from './components/chat/ChatStartScreen';
import { ChatPanel } from './components/chat/ChatPanel';
import { PaginatedFormModal } from './components/forms/PaginatedFormModal';
import { AuthGate } from './components/auth/AuthGate';
import type { AppView, DiagramTab, FormAnswerMap, FormRequest, Message } from './types';
import type { AuthSession } from './types/auth';
import { clearAuthSession, readAuthSession, saveAuthSession } from './lib/auth';
import {
  getConversationMessages,
  listConversations,
  streamChatMessage,
  submitFormAnswers,
  type ConversationSummary,
} from './lib/chatApi';
import {
  appendChunkToBotMessage,
  appendUserAndBotPlaceholder,
  attachFormRequestToBotMessage,
  failBotMessage,
  finalizeBotMessage,
} from './lib/streamingMessageState';
import './index.css';

function logApp(message: string, details?: unknown) {
  if (details === undefined) {
    console.log(`[App] ${message}`);
    return;
  }
  console.log(`[App] ${message}`, details);
}

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [view, setView] = useState<AppView>('start');
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messagesByConversation, setMessagesByConversation] = useState<Record<string, Message[]>>({});
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [diagramState, setDiagramState] = useState({ tabs: [] as DiagramTab[], activeTabId: null as string | null });
  const [isCanvasHidden, setIsCanvasHidden] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeFormRequest, setActiveFormRequest] = useState<FormRequest | null>(null);
  const [formSubmitError, setFormSubmitError] = useState<string | null>(null);
  const { tabs: diagramTabs, activeTabId: activeDiagramTabId } = diagramState;
  const hasVisibleCanvas = diagramTabs.length > 0 && !isCanvasHidden;

  useEffect(() => {
    const persistedSession = readAuthSession();
    setSession(persistedSession);
    logApp('Session loaded from storage', {
      hasSession: Boolean(persistedSession),
      hasEmail: Boolean(persistedSession?.email),
    });
  }, []);

  useEffect(() => {
    if (!session) return;
    void refreshConversations(session.accessToken);
  }, [session]);

  function handleSignOut() {
    logApp('Signing out');
    clearAuthSession();
    setSession(null);
    setMessages([]);
    setMessagesByConversation({});
    setConversations([]);
    setActiveConversationId(null);
    setView('start');
    setActiveFormRequest(null);
  }

  function fallbackTitle(firstMessage: string): string {
    const cleaned = firstMessage.trim().replace(/\s+/g, ' ');
    return cleaned.length > 60 ? `${cleaned.slice(0, 60)}...` : cleaned || 'New conversation';
  }

  async function refreshConversations(accessToken: string) {
    try {
      const items = await listConversations(accessToken);
      setConversations(items);
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 401) {
        handleUnauthorized();
      }
    }
  }

  function handleUnauthorized() {
    handleSignOut();
  }

  function saveDiagramState(nextTabs: DiagramTab[], nextActiveTabId: string | null) {
    setDiagramState({ tabs: nextTabs, activeTabId: nextActiveTabId });
  }

  function applyBotDiagrams(nextMessages: Message[]) {
    const botMessages = nextMessages.filter((message) => message.role === 'bot');

    const latestFormRequest = [...botMessages]
      .reverse()
      .find((message) => message.formRequest)?.formRequest;
    if (latestFormRequest) {
      setActiveFormRequest(latestFormRequest);
      setFormSubmitError(null);
    }
  }

  function handleSignIn(token: string, email?: string) {
    logApp('Signing in', {
      hasEmail: Boolean(email),
      tokenLength: token.length,
    });
    const nextSession: AuthSession = { accessToken: token, email };
    saveAuthSession(nextSession);
    setSession(nextSession);
  }

  async function handleSubmit(message: string) {
    logApp('Start screen submit', { messageLength: message.length });
    setView('chat');
    setActiveConversationId(null);
    await handleSend(message);
  }

  async function handleSend(text: string) {
    if (!session) {
      logApp('Blocked send because session is missing');
      return;
    }

    setFormSubmitError(null);
    logApp('Sending message', {
      messageLength: text.length,
      currentView: view,
      activeConversationId,
    });
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    };
    const botMessageId = (Date.now() + 1).toString();
    setMessages((prev) => appendUserAndBotPlaceholder(prev, userMessage, botMessageId));
    setIsSending(true);

    try {
      const result = await streamChatMessage({
        message: text,
        accessToken: session.accessToken,
        conversationId: activeConversationId,
        onChunk: (textChunk) => {
          setMessages((prev) => appendChunkToBotMessage(prev, botMessageId, textChunk));
        },
        onFormRequest: (formRequest) => {
          setMessages((prev) => attachFormRequestToBotMessage(prev, botMessageId, formRequest));
          setActiveFormRequest(formRequest);
          setFormSubmitError(null);
        },
      });
      logApp('Received chat stream result', {
        textLength: result.text.length,
        hasFormRequest: Boolean(result.formRequest),
      });
      setMessages((prev) => {
        const next = finalizeBotMessage(prev, botMessageId, result.text, result.formRequest);
        applyBotDiagrams(next);
        const resolvedConversationId = result.conversationId ?? activeConversationId;
        if (resolvedConversationId) {
          setMessagesByConversation((existing) => ({
            ...existing,
            [resolvedConversationId]: next,
          }));
        }
        return next;
      });
      if (result.conversationId && !activeConversationId) {
        setActiveConversationId(result.conversationId);
        setConversations((prev) => [
          {
            id: result.conversationId as string,
            title: fallbackTitle(text),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          ...prev.filter((item) => item.id !== result.conversationId),
        ]);
      }
      await refreshConversations(session.accessToken);
    } catch (error) {
      const status = (error as { status?: number }).status;
      logApp('Chat send failed', {
        status,
        error,
      });
      console.error('[App] Chat send failed (raw error)', error);
      if (status === 401) {
        handleUnauthorized();
        return;
      }

      setMessages((prev) =>
        failBotMessage(prev, botMessageId, 'I hit a connection issue while contacting the backend. Please try again.')
      );
    } finally {
      setIsSending(false);
    }
  }

  async function handleConversationSelect(conversationId: string) {
    if (!session) return;
    setView('chat');
    setActiveConversationId(conversationId);

    const cached = messagesByConversation[conversationId];
    if (cached) {
      setMessages(cached);
      return;
    }

    try {
      const conversationMessages = await getConversationMessages(conversationId, session.accessToken);
      const hydrated: Message[] = conversationMessages.map((item) => ({
        id: item.id,
        role: item.role,
        content: item.content,
      }));
      setMessages(hydrated);
      setMessagesByConversation((prev) => ({ ...prev, [conversationId]: hydrated }));
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 401) {
        handleUnauthorized();
      }
    }
  }

  function handleNewChat() {
    setView('chat');
    setMessages([]);
    setActiveConversationId(null);
    setActiveFormRequest(null);
    setFormSubmitError(null);
  }

  function handleFormClose() {
    setActiveFormRequest(null);
    setFormSubmitError(null);
  }

  async function handleFormSubmit(formId: string, answers: FormAnswerMap) {
    if (!session) {
      logApp('Blocked form submit because session is missing');
      handleUnauthorized();
      return;
    }

    setFormSubmitError(null);
    logApp('Submitting form', {
      formId,
      fieldCount: Object.keys(answers).length,
    });
    try {
      await submitFormAnswers({
        formId,
        answers,
        accessToken: session.accessToken,
      });
      setActiveFormRequest(null);
    } catch (error) {
      const status = (error as { status?: number }).status;
      logApp('Form submit failed', {
        status,
        error,
      });
      console.error('[App] Form submit failed (raw error)', error);
      if (status === 401) {
        handleUnauthorized();
        return;
      }
      setFormSubmitError('Unable to submit the form to the backend. Please try again.');
    }
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

  if (!session) {
    return <AuthGate onSignIn={handleSignIn} />;
  }

  const sidebarConversations = conversations.map((conversation) => ({
    id: conversation.id,
    title: conversation.title,
    active: conversation.id === activeConversationId,
  }));

  return (
    <MainLayout
      sidebarCollapsed={sidebarCollapsed}
      onSidebarToggle={handleSidebarToggle}
      conversations={sidebarConversations}
      onConversationSelect={handleConversationSelect}
      onNewChat={handleNewChat}
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
      {formSubmitError && (
        <div className="absolute bottom-4 right-4 z-20 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-md">
          {formSubmitError}
        </div>
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
