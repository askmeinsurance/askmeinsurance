import type { FormRequest, Message } from '../types';

export function appendUserAndBotPlaceholder(prev: Message[], userMessage: Message, botMessageId: string): Message[] {
  return [
    ...prev,
    userMessage,
    {
      id: botMessageId,
      role: 'bot',
      content: '',
    },
  ];
}

export function appendChunkToBotMessage(prev: Message[], botMessageId: string, textChunk: string): Message[] {
  return prev.map((message) =>
    message.id === botMessageId ? { ...message, content: message.content + textChunk } : message
  );
}

export function attachFormRequestToBotMessage(
  prev: Message[],
  botMessageId: string,
  formRequest: FormRequest
): Message[] {
  return prev.map((message) => (message.id === botMessageId ? { ...message, formRequest } : message));
}

export function finalizeBotMessage(
  prev: Message[],
  botMessageId: string,
  finalText: string,
  formRequest?: FormRequest
): Message[] {
  return prev.map((message) =>
    message.id === botMessageId
      ? {
          ...message,
          content: finalText,
          formRequest: formRequest ?? message.formRequest,
        }
      : message
  );
}

export function failBotMessage(prev: Message[], botMessageId: string, fallbackText: string): Message[] {
  return prev.map((message) => (message.id === botMessageId ? { ...message, content: fallbackText } : message));
}
