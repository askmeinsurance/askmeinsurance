import { useEffect, useState } from 'react';
import type { AuthChangeEvent, Session } from '@supabase/supabase-js';
import { MainLayout } from './components/layout/MainLayout';
import { ChatStartScreen } from './components/chat/ChatStartScreen';
import { ChatPanel } from './components/chat/ChatPanel';
import { AuthGate } from './components/auth/AuthGate';
import { DisclaimerModal } from './components/disclaimer/DisclaimerModal';
import type { AppView, DiagramTab, Message } from './types';
import type { AuthSession, EmailPasswordCredentials } from './types/auth';
import {
  clearAuthSession,
  readAuthSession,
  saveAuthSession,
  toAuthSessionFromSupabaseSession,
} from './lib/auth';
import { getSupabaseClient } from './lib/supabase';
import {
  deleteConversation,
  getConversationMessages,
  listConversations,
  streamChatMessage,
  type ConversationSummary,
} from './lib/chatApi';
import {
  appendChunkToBotMessage,
  appendUserAndBotPlaceholder,
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

function toFriendlySignUpError(error: unknown): Error {
  const fallback = new Error('Unable to create your account. Please try again.');
  if (!(error instanceof Error)) return fallback;

  const message = error.message.toLowerCase();
  if (
    message.includes('already registered') ||
    message.includes('already exists') ||
    message.includes('user already') ||
    message.includes('email address is already')
  ) {
    return new Error('An account already exists for this email address. Please sign in instead.');
  }
  if (message.includes('rate limit') || message.includes('too many requests')) {
    return new Error('Too many sign-up attempts right now. Please wait a moment and try again.');
  }

  return error;
}

function toFriendlySignInError(error: unknown): Error {
  const fallback = new Error('Unable to sign in. Please try again.');
  if (!(error instanceof Error)) return fallback;

  const message = error.message.toLowerCase();
  if (message.includes('email not confirmed') || message.includes('not confirmed')) {
    return new Error('This account is not confirmed yet. Please verify the email or ask an admin to confirm your user.');
  }

  return error;
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
  const [authWarning, setAuthWarning] = useState<string | null>(null);
  const [disclaimerAgreed, setDisclaimerAgreed] = useState(false);
  const [showDisclaimerModal, setShowDisclaimerModal] = useState(false);
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
    if (!session) {
      document.title = 'AskMeInsurance — AI Insurance Advisor for Singapore';
    } else {
      document.title = 'Chat — AskMeInsurance';
    }
  }, [session]);

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      logApp('Supabase client unavailable during auth bootstrap');
      return;
    }

    let isMounted = true;

    void supabase.auth.getSession().then((result) => {
      const data = result?.data;
      const error = result?.error;
      if (!isMounted) return;
      if (error) {
        logApp('supabase.auth.getSession returned error', error);
        return;
      }
      const supabaseSession = data.session;
      logApp('supabase.auth.getSession resolved', {
        hasSession: Boolean(supabaseSession),
        hasUser: Boolean(supabaseSession?.user?.id),
      });

      if (supabaseSession) {
        const nextSession = toAuthSessionFromSupabaseSession(supabaseSession);
        saveAuthSession(nextSession);
        setSession(nextSession);
        return;
      }

      setSession((current) => {
        if (current?.source === 'supabase') {
          clearAuthSession();
          return null;
        }
        return current;
      });
    });

    const { data } = supabase.auth.onAuthStateChange((_event: AuthChangeEvent, supabaseSession: Session | null) => {
      if (!isMounted) return;
      logApp('Supabase auth state changed', {
        event: _event,
        hasSession: Boolean(supabaseSession),
        hasUser: Boolean(supabaseSession?.user?.id),
      });

      if (supabaseSession) {
        const nextSession = toAuthSessionFromSupabaseSession(supabaseSession);
        saveAuthSession(nextSession);
        setSession(nextSession);
        return;
      }

      setSession((current) => {
        if (current?.source === 'supabase') {
          clearAuthSession();
          return null;
        }
        return current;
      });
    });

    return () => {
      isMounted = false;
      data.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!session) return;
    void refreshConversations(session.accessToken);
  }, [session]);

  function handleDisclaimerCheckboxClick() {
    setShowDisclaimerModal(true);
  }

  function handleDisclaimerAgree() {
    setDisclaimerAgreed(true);
    setShowDisclaimerModal(false);
  }

  function handleDisclaimerExit() {
    handleSignOut();
  }

  function handleSignOut() {
    logApp('Signing out');
    const supabase = getSupabaseClient();
    if (supabase) {
      void supabase.auth.signOut();
    }
    clearAuthSession();
    setSession(null);
    setMessages([]);
    setMessagesByConversation({});
    setConversations([]);
    setActiveConversationId(null);
    setView('start');
  }

  function fallbackTitle(firstMessage: string): string {
    const cleaned = firstMessage.trim().replace(/\s+/g, ' ');
    return cleaned.length > 60 ? `${cleaned.slice(0, 60)}...` : cleaned || 'New conversation';
  }

  async function refreshConversations(accessToken: string) {
    try {
      const items = await listConversations(accessToken);
      setConversations(items);
      setAuthWarning(null);
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 401) {
        logApp('Conversations refresh returned 401 after sign-in; keeping session and showing warning');
        setAuthWarning('Signed in, but backend auth verification failed. Check backend Supabase JWT settings.');
        return;
      }
      setAuthWarning('Unable to load conversations right now.');
    }
  }

  function handleUnauthorized() {
    handleSignOut();
  }

  function saveDiagramState(nextTabs: DiagramTab[], nextActiveTabId: string | null) {
    setDiagramState({ tabs: nextTabs, activeTabId: nextActiveTabId });
  }

  async function handleEmailPasswordSignIn(credentials: EmailPasswordCredentials) {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error('Supabase auth is not configured.');
    }
    logApp('Sign in requested', {
      email: credentials.email,
      passwordLength: credentials.password.length,
    });

    const { data, error } = await supabase.auth.signInWithPassword(credentials);
    logApp('supabase.auth.signInWithPassword resolved', {
      hasError: Boolean(error),
      hasSession: Boolean(data.session),
      hasUser: Boolean(data.user?.id),
    });
    if (error || !data.session) {
      logApp('Sign in failed', error ?? 'No session returned');
      throw toFriendlySignInError(error ?? new Error('Sign in failed.'));
    }

    const nextSession = toAuthSessionFromSupabaseSession(data.session);
    saveAuthSession(nextSession);
    setSession(nextSession);
  }

  async function handleEmailPasswordSignUp(credentials: EmailPasswordCredentials) {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error('Supabase auth is not configured.');
    }
    logApp('Sign up requested', {
      email: credentials.email,
      passwordLength: credentials.password.length,
    });

    const { data, error } = await supabase.auth.signUp(credentials);
    logApp('supabase.auth.signUp resolved', {
      hasError: Boolean(error),
      hasSession: Boolean(data.session),
      hasUser: Boolean(data.user?.id),
      userId: data.user?.id ?? null,
      emailConfirmedAt: data.user?.email_confirmed_at ?? null,
    });
    if (error) {
      logApp('Sign up failed', error);
      throw toFriendlySignUpError(error);
    }

    // Supabase can return a user with zero identities and no explicit error for existing emails.
    const identities = data.user?.identities ?? [];
    if (data.user && identities.length === 0) {
      logApp('Sign up indicates existing account via empty identities response', {
        userId: data.user.id,
        email: data.user.email,
      });
      throw new Error('An account already exists for this email address. Please sign in instead.');
    }

    if (data.session) {
      const nextSession = toAuthSessionFromSupabaseSession(data.session);
      saveAuthSession(nextSession);
      setSession(nextSession);
      logApp('Sign up completed with active session');
      return;
    }

    logApp('Sign up completed without session; attempting immediate sign-in');
    const signInResult = await supabase.auth.signInWithPassword(credentials);
    logApp('Post-signup signInWithPassword resolved', {
      hasError: Boolean(signInResult.error),
      hasSession: Boolean(signInResult.data.session),
      hasUser: Boolean(signInResult.data.user?.id),
    });

    if (signInResult.error || !signInResult.data.session) {
      throw (
        toFriendlySignUpError(signInResult.error) ??
        new Error('Account created, but sign-in requires email verification before continuing.')
      );
    }

    const nextSession = toAuthSessionFromSupabaseSession(signInResult.data.session);
    saveAuthSession(nextSession);
    setSession(nextSession);
    logApp('Post-signup sign-in completed with active session');
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
      });
      logApp('Received chat stream result', {
        textLength: result.text.length,
      });
      setMessages((prev) => {
        const next = finalizeBotMessage(prev, botMessageId, result.text);
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

  async function handleConversationDelete(conversationId: string) {
    if (!session) return;

    const target = conversations.find((item) => item.id === conversationId);
    const title = target?.title ?? 'this conversation';
    const confirmed = window.confirm(`Delete "${title}"? This cannot be undone.`);
    if (!confirmed) return;

    try {
      await deleteConversation(conversationId, session.accessToken);
      setConversations((prev) => prev.filter((item) => item.id !== conversationId));
      setMessagesByConversation((prev) => {
        const next = { ...prev };
        delete next[conversationId];
        return next;
      });

      if (activeConversationId === conversationId) {
        setView('chat');
        setActiveConversationId(null);
        setMessages([]);
      }
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status === 401) {
        handleUnauthorized();
        return;
      }
      setAuthWarning('Unable to delete conversation right now.');
    }
  }

  function handleNewChat() {
    setView('start');
    setMessages([]);
    setActiveConversationId(null);
    setDisclaimerAgreed(false);
    setShowDisclaimerModal(false);
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
    return (
      <AuthGate
        onEmailPasswordSignIn={handleEmailPasswordSignIn}
        onEmailPasswordSignUp={handleEmailPasswordSignUp}
      />
    );
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
      onConversationDelete={handleConversationDelete}
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
      {view === 'start' && (
        <ChatStartScreen
          onSubmit={handleSubmit}
          disclaimerAgreed={disclaimerAgreed}
          onDisclaimerCheckboxClick={handleDisclaimerCheckboxClick}
        />
      )}
      {view === 'chat' && (
        <ChatPanel
          messages={messages}
          onSend={handleSend}
          hasDiagramPanel={hasVisibleCanvas}
          isSending={isSending}
          disclaimerAgreed={disclaimerAgreed}
          onDisclaimerCheckboxClick={handleDisclaimerCheckboxClick}
        />
      )}
      {showDisclaimerModal && (
        <DisclaimerModal onAgree={handleDisclaimerAgree} onExit={handleDisclaimerExit} />
      )}
      {authWarning && (
        <div className="absolute bottom-4 left-4 z-20 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 shadow-md">
          {authWarning}
        </div>
      )}
    </MainLayout>
  );
}
