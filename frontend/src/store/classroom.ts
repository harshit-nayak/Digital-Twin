import { create } from 'zustand';
import type { ChatResponse } from '../services/chat';

export type ScientistId = 'einstein' | 'newton' | 'feynman' | 'tesla' | 'curie';

export type Message = {
  role: 'student' | 'scientist';
  text: string;
  response?: ChatResponse;
};

type ClassroomState = {
  scientist: ScientistId;
  timeline: string;
  sessionId: string;
  messages: Message[];
  setScientist: (scientist: ScientistId) => void;
  setTimeline: (timeline: string) => void;
  addMessage: (message: Message) => void;
};

export const useClassroom = create<ClassroomState>((set) => ({
  scientist: 'einstein',
  timeline: '1905',
  sessionId: crypto.randomUUID(),
  messages: [],
  setScientist: (scientist) => set({ scientist }),
  setTimeline: (timeline) => set({ timeline }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] }))
}));

