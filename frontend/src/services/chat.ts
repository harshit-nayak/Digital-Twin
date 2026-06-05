export type ChatSource = {
  id: string;
  title: string;
  scientist: string;
  score: number;
  timeline_start?: number | null;
  timeline_end?: number | null;
  excerpt: string;
};

export type ChatResponse = {
  message: string;
  scientist: string;
  sources: ChatSource[];
  timeline_context?: string | null;
  emotion: string;
  memory_updates: string[];
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export async function chat(input: {
  session_id: string;
  scientist: string;
  message: string;
  timeline?: string;
}): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input)
  });

  if (!response.ok) {
    throw new Error(`Chat failed with status ${response.status}`);
  }
  return response.json();
}
