import { create } from 'zustand'

const API_BASE = 'http://localhost:8000'

export const useStore = create((set, get) => ({
  // ── Active session ───────────────────────────────────────
  scientist: null,          // { id, name, birth_year, death_year, domain, ... }
  timelineYear: null,       // selected milestone year
  sessionId: null,
  mode: 'chat',             // chat | quiz | gedanken | modern_react

  // ── Conversation ────────────────────────────────────────
  messages: [],             // [{ role:'user'|'assistant', text, emotion, sources, faithfulness }]
  isLoading: false,
  streamingText: '',        // partial text during WS streaming

  // ── Memory ──────────────────────────────────────────────
  memories: [],
  userProfile: null,
  sessions: [],

  // ── UI state ────────────────────────────────────────────
  sidebarTab: 'profile',    // profile | memories | corpus
  lastSources: [],
  lastEmotion: 'NEUTRAL',
  currentEmotion: 'NEUTRAL',

  // ── Scientists registry ─────────────────────────────────
  scientists: [],
  scientistsLoaded: false,

  // ─────────────────────────────────────────────────────────
  // Actions
  // ─────────────────────────────────────────────────────────

  setScientist: (scientist) => set({
    scientist,
    messages: [],
    memories: [],
    lastSources: [],
    currentEmotion: 'NEUTRAL',
    streamingText: '',
  }),

  setTimelineYear: (year) => set({ timelineYear: year }),

  setMode: (mode) => set({ mode }),

  setSidebarTab: (tab) => set({ sidebarTab: tab }),

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  setLoading: (v) => set({ isLoading: v }),

  setStreamingText: (text) => set({ streamingText: text }),

  setEmotion: (emotion) => set({ currentEmotion: emotion }),

  // ─────────────────────────────────────────────────────────
  // API calls
  // ─────────────────────────────────────────────────────────

  loadScientists: async () => {
    try {
      const resp = await fetch(`${API_BASE}/scientists`)
      const data = await resp.json()
      // The backend returns { "scientists": [...] }, so we need to set data.scientists
      const list = Array.isArray(data) ? data : (data.scientists || [])
      set({ scientists: list, scientistsLoaded: true })
    } catch (e) {
      console.error('Failed to load scientists:', e)
    }
  },

  loadMemories: async () => {
    const { scientist } = get()
    if (!scientist) return
    try {
      const resp = await fetch(`${API_BASE}/memory/user123/${scientist.id}`)
      const data = await resp.json()

      // If data.memories is grouped by memory_type (object), flatten it and inject memory_type
      let flatMemories = []
      if (data.memories && typeof data.memories === 'object' && !Array.isArray(data.memories)) {
        for (const [mtype, items] of Object.entries(data.memories)) {
          if (Array.isArray(items)) {
            items.forEach(item => {
              flatMemories.push({
                ...item,
                memory_type: mtype
              })
            })
          }
        }
      } else {
        flatMemories = data.memories || []
      }

      set({
        memories:    flatMemories,
        userProfile: data.profile  || null,
        sessions:    data.sessions || [],
      })
    } catch (e) {
      console.error('Failed to load memories:', e)
    }
  },

  deleteMemory: async (memId) => {
    const { scientist } = get()
    if (!scientist) return
    await fetch(`${API_BASE}/memory/user123/${scientist.id}/${memId}`, {
      method: 'DELETE'
    })
    get().loadMemories()
  },

  clearMemories: async () => {
    const { scientist } = get()
    if (!scientist) return
    await fetch(`${API_BASE}/memory/user123/${scientist.id}`, {
      method: 'DELETE'
    })
    set({ memories: [], sessions: [] })
  },

  // Send a chat message via WebSocket streaming
  sendMessage: async (query) => {
    const { scientist, timelineYear, mode, addMessage, setLoading, setStreamingText, setEmotion, loadMemories } = get()
    if (!scientist || !query.trim()) return

    addMessage({ role: 'user', text: query })
    setLoading(true)
    setStreamingText('')

    const payload = {
      user_id:      'user123',
      scientist_id: scientist.id,
      timeline_year: timelineYear,
      query,
      mode,
    }

    // Try WebSocket streaming first, fallback to REST
    const wsUrl = `ws://localhost:8000/chat/stream`
    let ws

    try {
      ws = new WebSocket(wsUrl)
      let fullText = ''
      let metaReceived = false

      ws.onopen = () => ws.send(JSON.stringify(payload))

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'chunk') {
          fullText += msg.content
          setStreamingText(fullText)
        } else if (msg.type === 'meta') {
          metaReceived = true
          const meta = typeof msg.content === 'string' ? JSON.parse(msg.content) : msg.content
          setEmotion(meta.emotion_tag || 'NEUTRAL')
          addMessage({
            role:        'assistant',
            text:        fullText,
            emotion:     meta.emotion_tag     || 'NEUTRAL',
            sources:     meta.sources         || [],
            faithfulness: meta.faithfulness_score ?? null,
            rewritten:   meta.rewritten_query || null,
          })
          set({ lastSources: meta.sources || [], lastEmotion: meta.emotion_tag || 'NEUTRAL' })
          setStreamingText('')
          setLoading(false)
          loadMemories()
        } else if (msg.type === 'done') {
          if (!metaReceived && fullText) {
            addMessage({ role: 'assistant', text: fullText, emotion: 'NEUTRAL', sources: [], faithfulness: null })
            setStreamingText('')
          }
          setLoading(false)
        } else if (msg.type === 'error') {
          addMessage({ role: 'assistant', text: `[Error: ${msg.content}]`, emotion: 'NEUTRAL', sources: [] })
          setStreamingText('')
          setLoading(false)
        }
      }

      ws.onerror = async () => {
        // Fallback to REST POST
        try {
          const resp = await fetch(`${API_BASE}/chat`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
          })
          const data = await resp.json()
          setEmotion(data.emotion_tag || 'NEUTRAL')
          addMessage({
            role:        'assistant',
            text:        data.response_text || '[No response]',
            emotion:     data.emotion_tag   || 'NEUTRAL',
            sources:     data.sources       || [],
            faithfulness: data.faithfulness_score ?? null,
          })
          set({ lastSources: data.sources || [] })
        } catch (err) {
          addMessage({ role: 'assistant', text: '[Backend unreachable]', emotion: 'NEUTRAL', sources: [] })
        }
        setStreamingText('')
        setLoading(false)
        loadMemories()
      }

      ws.onclose = () => {
        if (get().isLoading) setLoading(false)
      }

    } catch (e) {
      setLoading(false)
    }
  },
}))

export const API_BASE_URL = API_BASE
