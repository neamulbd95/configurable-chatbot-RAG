// Mirrors ragchatbot.chat.schemas (backend) — keep in sync if the API changes.

export interface ChatRequest {
  message: string;
  session_id?: string | null;
  roles?: string[] | null;
}

export interface Citation {
  source_table: string | null;
  primary_key: string | null;
  chunk_id: string;
  similarity: number;
}

export interface ChatResponse {
  answer: string;
  session_id: string | null;
  citations: Citation[];
  grounded: boolean;
  confidence: number;
}

export type ChatRole = 'user' | 'assistant';

export interface ChatMessageView {
  role: ChatRole;
  content: string;
  citations?: Citation[];
  confidence?: number;
  grounded?: boolean;
  pending?: boolean;
  error?: string;
}
