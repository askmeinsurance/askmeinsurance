export interface ChatStreamResult {
  text: string;
  conversationId?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'bot';
  content: string;
  created_at: string;
}

function resolveApiBase(): string {
  const configured = import.meta.env.VITE_BACKEND_BASE_URL?.trim().replace(/\/+$/, '');
  if (configured) {
    return `${configured}/api/v1`;
  }

  // Dev-safe default: Vite runs on 5173 while backend runs on 8000.
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    return `http://${window.location.hostname}:8000/api/v1`;
  }

  // Production fallback for same-origin deployments.
  return '/api/v1';
}

const API_BASE = resolveApiBase();
const CHAT_ENDPOINT = `${API_BASE}/chat/stream`;
const CONVERSATIONS_ENDPOINT = `${API_BASE}/conversations`;

function logDebug(message: string, details?: unknown) {
  if (details === undefined) {
    console.log(`[chatApi] ${message}`);
    return;
  }
  console.log(`[chatApi] ${message}`, details);
}

function extractTextFromUnknown(input: unknown): string {
  if (typeof input === 'string') return input;
  if (Array.isArray(input)) {
    const parts = input
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const rec = item as Record<string, unknown>;
          if (rec.type === 'text' && typeof rec.text === 'string') return rec.text;
        }
        return '';
      })
      .filter((part) => part.length > 0);
    return parts.join('\n');
  }
  if (input && typeof input === 'object') {
    const rec = input as Record<string, unknown>;
    if (rec.type === 'text' && typeof rec.text === 'string') return rec.text;
  }
  return '';
}

function parsePossibleUuid(value: string): string | null {
  const trimmed = value.trim();
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(trimmed) ? trimmed : null;
}

export async function streamChatMessage(opts: {
  message: string;
  accessToken: string;
  conversationId?: string | null;
  signal?: AbortSignal;
  onChunk?: (textChunk: string) => void;
}): Promise<ChatStreamResult> {
  const payload: { message: string; conversation_id?: string } = {
    message: opts.message,
  };

  const normalizedConversationId = opts.conversationId ? parsePossibleUuid(opts.conversationId) : null;
  if (normalizedConversationId) {
    payload.conversation_id = normalizedConversationId;
  }

  logDebug('Sending stream request', {
    endpoint: CHAT_ENDPOINT,
    hasConversationId: Boolean(normalizedConversationId),
    messageLength: opts.message.length,
  });

  const response = await fetch(CHAT_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${opts.accessToken}`,
    },
    body: JSON.stringify(payload),
    signal: opts.signal,
  });

  const requestId = response.headers.get('x-request-id');
  logDebug('Stream response received', {
    status: response.status,
    ok: response.ok,
    hasBody: Boolean(response.body),
    requestId,
  });

  if (!response.ok || !response.body) {
    const err = new Error(`Chat stream failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();

  let buffer = '';
  let messageText = '';
  let conversationId: string | undefined;
  let eventCount = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const eventBlock of events) {
      eventCount += 1;
      const lines = eventBlock.split('\n');
      const eventType = lines.find((line) => line.startsWith('event:'))?.replace('event:', '').trim();
      const dataLine = lines.find((line) => line.startsWith('data:'));
      if (!dataLine) continue;

      const rawData = dataLine.replace('data:', '').trim();
      if (!rawData) continue;

      try {
        const parsed = JSON.parse(rawData) as Record<string, unknown>;

        if (eventType === 'chunk') {
          const chunkText = extractTextFromUnknown(parsed.text);
          if (chunkText.length > 0) {
            messageText += chunkText;
            opts.onChunk?.(chunkText);
          }
        }

        if (eventType === 'meta') {
          const metaConversationId = parsed.conversation_id;
          if (typeof metaConversationId === 'string' && metaConversationId.length > 0) {
            conversationId = metaConversationId;
          }
        }
      } catch {
        logDebug('Skipping malformed SSE event block');
        continue;
      }
    }
  }

  logDebug('Stream parsing complete', {
    requestId,
    eventCount,
    responseTextLength: messageText.length,
  });

  if (!messageText.trim()) {
    messageText = 'I could not generate a response right now. Please try again.';
  }

  return {
    text: messageText,
    conversationId,
  };
}

export async function listConversations(accessToken: string): Promise<ConversationSummary[]> {
  const response = await fetch(CONVERSATIONS_ENDPOINT, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const err = new Error(`List conversations failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }
  return (await response.json()) as ConversationSummary[];
}

export async function getConversationMessages(
  conversationId: string,
  accessToken: string,
): Promise<ConversationMessage[]> {
  const normalizedConversationId = parsePossibleUuid(conversationId);
  if (!normalizedConversationId) {
    throw new Error('Conversation ID is not a valid UUID');
  }

  const response = await fetch(`${CONVERSATIONS_ENDPOINT}/${normalizedConversationId}/messages`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const err = new Error(`Get conversation messages failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }
  return (await response.json()) as ConversationMessage[];
}

export async function deleteConversation(conversationId: string, accessToken: string): Promise<void> {
  const normalizedConversationId = parsePossibleUuid(conversationId);
  if (!normalizedConversationId) {
    throw new Error('Conversation ID is not a valid UUID');
  }

  const response = await fetch(`${CONVERSATIONS_ENDPOINT}/${normalizedConversationId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    const err = new Error(`Delete conversation failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }
}
