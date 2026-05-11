export type MessageRole = 'user' | 'bot';

export type FormFieldType = 'text' | 'textarea' | 'select' | 'radio' | 'checkbox';

export interface FormOption {
  label: string;
  value: string;
}

export interface FormField {
  id: string;
  label: string;
  type: FormFieldType;
  required?: boolean;
  placeholder?: string;
  options?: FormOption[];
}

export interface FormPage {
  id: string;
  title: string;
  description?: string;
  fields: FormField[];
}

export interface FormRequest {
  id: string;
  title: string;
  description?: string;
  submitLabel?: string;
  pages: FormPage[];
}

export type FormAnswerValue = string | boolean | string[];
export type FormAnswerMap = Record<string, FormAnswerValue>;

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
  formRequest?: FormRequest;
  thinking?: string;
}

export type AppView = 'start' | 'chat';
