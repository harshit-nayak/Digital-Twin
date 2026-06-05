import { motion, AnimatePresence } from 'framer-motion'
import './EmotionAvatar.css'

const EMOTION_DATA = {
  EXCITED:       { icon: '✨', color: '#f5e86e', label: 'Excited',       bg: 'rgba(245,232,110,0.1)'  },
  CONTEMPLATIVE: { icon: '💭', color: '#a8c4e0', label: 'Contemplative', bg: 'rgba(168,196,224,0.1)' },
  AMUSED:        { icon: '😄', color: '#a8e0a8', label: 'Amused',        bg: 'rgba(168,224,168,0.1)'  },
  SKEPTICAL:     { icon: '🤔', color: '#e0c0a8', label: 'Skeptical',     bg: 'rgba(224,192,168,0.1)'  },
  SAD:           { icon: '😔', color: '#b0b8d0', label: 'Sad',            bg: 'rgba(176,184,208,0.1)'  },
  NEUTRAL:       { icon: '🧠', color: '#f0ede4', label: 'Focused',       bg: 'rgba(240,237,228,0.08)' },
  PASSIONATE:    { icon: '🔥', color: '#e8a0a0', label: 'Passionate',    bg: 'rgba(232,160,160,0.1)'  },
}

// Einstein's known quotes per emotion state
const EMOTION_QUOTES = {
  EXCITED:       '"Imagination is more important than knowledge."',
  CONTEMPLATIVE: '"The important thing is not to stop questioning."',
  AMUSED:        '"If you can\'t explain it simply, you don\'t understand it well enough."',
  SKEPTICAL:     '"God does not play dice with the universe."',
  SAD:           '"Only a life lived for others is a life worthwhile."',
  NEUTRAL:       '"A person who never made a mistake never tried anything new."',
  PASSIONATE:    '"Great spirits have always encountered violent opposition from mediocre minds."',
}

export default function EmotionAvatar({ emotion = 'NEUTRAL', scientistId = 'einstein' }) {
  const data = EMOTION_DATA[emotion] || EMOTION_DATA.NEUTRAL

  return (
    <div className="avatar-wrap">
      <p className="avatar-label">Emotional State</p>

      {/* Avatar circle */}
      <AnimatePresence mode="wait">
        <motion.div
          key={emotion}
          className="avatar-circle"
          style={{ background: data.bg, borderColor: data.color + '40' }}
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.85, opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <motion.span
            className="avatar-icon"
            animate={{ rotate: [0, -5, 5, 0] }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            {data.icon}
          </motion.span>
          <div className="avatar-glow" style={{ background: data.color + '20' }} />
        </motion.div>
      </AnimatePresence>

      {/* Emotion label */}
      <AnimatePresence mode="wait">
        <motion.p
          key={emotion + '-label'}
          className="avatar-emotion-name"
          style={{ color: data.color }}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
        >
          {data.label}
        </motion.p>
      </AnimatePresence>

      {/* Contextual quote */}
      <AnimatePresence mode="wait">
        <motion.blockquote
          key={emotion + '-quote'}
          className="avatar-quote"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          {EMOTION_QUOTES[emotion] || EMOTION_QUOTES.NEUTRAL}
        </motion.blockquote>
      </AnimatePresence>

      {/* Emotion indicator dots */}
      <div className="avatar-emotions-grid">
        {Object.entries(EMOTION_DATA).map(([key, val]) => (
          <div
            key={key}
            className={`avatar-emotion-dot ${key === emotion ? 'active' : ''}`}
            style={{ '--dot-color': val.color }}
            title={val.label}
          >
            <span>{val.icon}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
