export type MessageRole = 'user' | 'bot';

export interface DiagramPayload {
  elements: readonly unknown[];
  appState?: unknown;
  files?: unknown;
}

export interface DiagramTab {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  diagram: DiagramPayload;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  hasDiagram?: boolean;
  diagramTitle?: string;
  diagramData?: DiagramPayload;
  thinking?: string;
}

export type AppView = 'start' | 'chat';
