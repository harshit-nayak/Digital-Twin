import './ModeSelector.css'
import { useStore } from '../store'

const MODES = [
  { id: 'chat',         label: 'Chat',      icon: '💬', desc: 'Open conversation'       },
  { id: 'quiz',         label: 'Quiz',      icon: '❓', desc: 'Socratic questioning'     },
  { id: 'gedanken',     label: 'Gedanken',  icon: '🌀', desc: 'Thought experiment mode'  },
  { id: 'modern_react', label: 'React',     icon: '⚡', desc: 'How would you react today?' },
]

export default function ModeSelector() {
  const mode    = useStore(s => s.mode)
  const setMode = useStore(s => s.setMode)
  const current = MODES.find(m => m.id === mode) || MODES[0]

  return (
    <div className="mode-selector">
      {MODES.map(m => (
        <button
          key={m.id}
          id={`mode-${m.id}`}
          className={`mode-btn ${mode === m.id ? 'active' : ''}`}
          onClick={() => setMode(m.id)}
          title={m.desc}
        >
          <span className="mode-icon">{m.icon}</span>
          <span className="mode-label">{m.label}</span>
        </button>
      ))}
    </div>
  )
}
