import type { FormAnswerMap, FormFieldType, FormOption, FormRequest } from '../types';

export interface ChatStreamResult {
  text: string;
  formRequest?: FormRequest;
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

function logDebug(message: string, details?: unknown) {
  if (details === undefined) {
    console.log(`[chatApi] ${message}`);
    return;
  }
  console.log(`[chatApi] ${message}`, details);
}

interface FormOptionWire {
  label?: unknown;
  value?: unknown;
}

interface FormFieldWire {
  id?: unknown;
  label?: unknown;
  type?: unknown;
  required?: unknown;
  placeholder?: unknown;
  options?: unknown;
}

interface FormPageWire {
  id?: unknown;
  title?: unknown;
  description?: unknown;
  fields?: unknown;
}

interface FormRequestWire {
  form_id?: unknown;
  title?: unknown;
  description?: unknown;
  submit_label?: unknown;
  pages?: unknown;
}

const FORM_FIELD_TYPES: FormFieldType[] = ['text', 'textarea', 'select', 'radio', 'checkbox'];

function parsePossibleUuid(value: string): string | null {
  const trimmed = value.trim();
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(trimmed) ? trimmed : null;
}

function mapFormRequestWireToUi(input: unknown): FormRequest | undefined {
  if (!input || typeof input !== 'object') return undefined;

  const wire = input as FormRequestWire;

  if (typeof wire.form_id !== 'string' || typeof wire.title !== 'string' || !Array.isArray(wire.pages)) {
    return undefined;
  }

  const pages = wire.pages
    .map((page): FormRequest['pages'][number] | null => {
      if (!page || typeof page !== 'object') return null;
      const pageWire = page as FormPageWire;

      if (typeof pageWire.id !== 'string' || typeof pageWire.title !== 'string' || !Array.isArray(pageWire.fields)) {
        return null;
      }

      const fields = pageWire.fields
        .map((field): FormRequest['pages'][number]['fields'][number] | null => {
          if (!field || typeof field !== 'object') return null;
          const fieldWire = field as FormFieldWire;

          if (
            typeof fieldWire.id !== 'string' ||
            typeof fieldWire.label !== 'string' ||
            typeof fieldWire.type !== 'string'
          ) {
            return null;
          }

          const options = Array.isArray(fieldWire.options)
            ? fieldWire.options
                .map((option): FormOption | null => {
                  if (!option || typeof option !== 'object') return null;
                  const optionWire = option as FormOptionWire;
                  if (typeof optionWire.label !== 'string' || typeof optionWire.value !== 'string') return null;
                  return { label: optionWire.label, value: optionWire.value };
                })
                .filter((option): option is FormOption => option !== null)
            : undefined;

          if (!FORM_FIELD_TYPES.includes(fieldWire.type as FormFieldType)) {
            return null;
          }

          return {
            id: fieldWire.id,
            label: fieldWire.label,
            type: fieldWire.type as FormFieldType,
            required: typeof fieldWire.required === 'boolean' ? fieldWire.required : undefined,
            placeholder: typeof fieldWire.placeholder === 'string' ? fieldWire.placeholder : undefined,
            options,
          };
        })
        .filter((field): field is FormRequest['pages'][number]['fields'][number] => field !== null);

      return {
        id: pageWire.id,
        title: pageWire.title,
        description: typeof pageWire.description === 'string' ? pageWire.description : undefined,
        fields,
      };
    })
    .filter((page): page is FormRequest['pages'][number] => page !== null);

  return {
    id: wire.form_id,
    title: wire.title,
    description: typeof wire.description === 'string' ? wire.description : undefined,
    submitLabel: typeof wire.submit_label === 'string' ? wire.submit_label : undefined,
    pages,
  };
}

export async function streamChatMessage(opts: {
  message: string;
  accessToken: string;
  conversationId?: string | null;
  signal?: AbortSignal;
  onChunk?: (textChunk: string) => void;
  onFormRequest?: (formRequest: FormRequest) => void;
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
  let latestFormRequest: FormRequest | undefined;
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
          const chunkText = parsed.text;
          if (typeof chunkText === 'string') {
            messageText += chunkText;
            opts.onChunk?.(chunkText);
          }
        }

        if (eventType === 'form_requested') {
          const mapped = mapFormRequestWireToUi(parsed);
          if (mapped) {
            latestFormRequest = mapped;
            opts.onFormRequest?.(mapped);
            logDebug('Received form_requested event');
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
    hasFormRequest: Boolean(latestFormRequest),
  });

  if (!messageText.trim()) {
    messageText = 'I could not generate a response right now. Please try again.';
  }

  return {
    text: messageText,
    formRequest: latestFormRequest,
  };
}

export async function submitFormAnswers(opts: {
  formId: string;
  answers: FormAnswerMap;
  accessToken: string;
}): Promise<void> {
  const uuid = parsePossibleUuid(opts.formId);
  if (!uuid) {
    throw new Error('Form ID is not a valid UUID for backend submission');
  }

  const endpoint = `${API_BASE}/forms/${uuid}/submit`;
  logDebug('Submitting form answers', {
    endpoint,
    formId: uuid,
    fieldCount: Object.keys(opts.answers).length,
  });

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${opts.accessToken}`,
    },
    body: JSON.stringify({ fields: opts.answers }),
  });

  logDebug('Form submit response', {
    status: response.status,
    ok: response.ok,
    requestId: response.headers.get('x-request-id'),
  });

  if (!response.ok) {
    const err = new Error(`Form submission failed with status ${response.status}`);
    (err as Error & { status?: number }).status = response.status;
    throw err;
  }
}
