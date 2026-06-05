import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store'
import './ScientistLobby.css'

// Hard-coded Einstein card since only Einstein is live
const SCIENTISTS = [
  {
    id: 'einstein',
    name: 'Albert Einstein',
    years: '1879 – 1955',
    domain: 'Theoretical Physics',
    specialty: 'Relativity · Quantum Theory · Photoelectric Effect',
    tagline: '"God does not play dice with the universe."',
    era: 'Modern Physics',
    status: 'live',
    color: '#d4a843',
    gradient: 'linear-gradient(135deg, #2a1f0a 0%, #1a2a0a 50%, #0a1a0a 100%)',
    portrait_bg: 'linear-gradient(160deg, #c8922e, #8a6010)',
  },
  {
    id: 'newton',
    name: 'Isaac Newton',
    years: '1643 – 1727',
    domain: 'Natural Philosophy',
    specialty: 'Classical Mechanics · Optics · Calculus',
    tagline: '"If I have seen further, it is by standing on the shoulders of giants."',
    era: 'Scientific Revolution',
    status: 'coming_soon',
    color: '#8ab4d4',
    gradient: 'linear-gradient(135deg, #0a1520 0%, #0a1a25 50%, #0a1015 100%)',
    portrait_bg: 'linear-gradient(160deg, #4a7090, #1a3550)',
  },
  {
    id: 'feynman',
    name: 'Richard Feynman',
    years: '1918 – 1988',
    domain: 'Quantum Physics',
    specialty: 'QED · Particle Physics · Nanotechnology',
    tagline: '"If you think you understand quantum mechanics, you don\'t understand quantum mechanics."',
    era: 'Nuclear Age',
    status: 'coming_soon',
    color: '#e89040',
    gradient: 'linear-gradient(135deg, #1a1000 0%, #201800 50%, #0a1000 100%)',
    portrait_bg: 'linear-gradient(160deg, #c06820, #703000)',
  },
  {
    id: 'curie',
    name: 'Marie Curie',
    years: '1867 – 1934',
    domain: 'Radioactivity',
    specialty: 'Polonium · Radium · X-Ray Research',
    tagline: '"Nothing in life is to be feared, only to be understood."',
    era: 'Age of Discovery',
    status: 'coming_soon',
    color: '#c080c8',
    gradient: 'linear-gradient(135deg, #150a20 0%, #1a0a25 50%, #0a0a15 100%)',
    portrait_bg: 'linear-gradient(160deg, #9040a0, #401060)',
  },
  {
    id: 'tesla',
    name: 'Nikola Tesla',
    years: '1856 – 1943',
    domain: 'Electrical Engineering',
    specialty: 'AC Power · Radio · Rotating Magnetic Fields',
    tagline: '"The present is theirs; the future, for which I really worked, is mine."',
    era: 'Gilded Age',
    status: 'coming_soon',
    color: '#60c0e0',
    gradient: 'linear-gradient(135deg, #00101a 0%, #001520 50%, #000a10 100%)',
    portrait_bg: 'linear-gradient(160deg, #2080b0, #004060)',
  },
]

// Emoji avatars for scientists (placeholders until real sprites)
const INITIALS = { einstein:'AE', newton:'IN', feynman:'RF', curie:'MC', tesla:'NT' }
const ICONS    = { einstein:'⚛', newton:'🍎', feynman:'🔬', curie:'☢', tesla:'⚡' }

export default function ScientistLobby() {
  const navigate       = useNavigate()
  const setScientist   = useStore(s => s.setScientist)
  const setTimelineYear= useStore(s => s.setTimelineYear)
  const scientists     = useStore(s => s.scientists)
  const [hovered, setHovered] = useState(null)

  const handleSelect = (sc) => {
    if (sc.status !== 'live') return
    setScientist(sc)
    // Default to latest available year
    const apiSc = scientists.find(s => s.id === sc.id)
    if (apiSc?.timelines?.length) {
      setTimelineYear(apiSc.timelines[apiSc.timelines.length - 1].year)
    } else {
      setTimelineYear(1955)
    }
    navigate(`/room/${sc.id}`)
  }

  return (
    <div className="lobby-root">
      {/* Background particles */}
      <div className="lobby-bg" />

      {/* Header */}
      <motion.header
        className="lobby-header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <div className="lobby-header-inner">
          <div className="lobby-logo">
            <span className="lobby-logo-icon">⚛</span>
            <div>
              <h1 className="lobby-title chalk-text">Digital Twin Physics Academy</h1>
              <p className="lobby-subtitle">Learn from the scientists who changed the world</p>
            </div>
          </div>
          <div className="lobby-status-pill">
            <span className="status-dot live" />
            <span>1 Scientist Live</span>
          </div>
        </div>
      </motion.header>

      {/* Intro */}
      <motion.div
        className="lobby-intro"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3, duration: 0.6 }}
      >
        <p>Choose a scientific mind to enter their classroom. Every answer is grounded in their actual writings. Every conversation remembers.</p>
      </motion.div>

      {/* Scientist Grid */}
      <div className="lobby-grid">
        {SCIENTISTS.map((sc, i) => (
          <motion.div
            key={sc.id}
            className={`scientist-card ${sc.status}`}
            style={{ '--sc-color': sc.color, '--sc-gradient': sc.gradient }}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * i + 0.3, duration: 0.5 }}
            onHoverStart={() => setHovered(sc.id)}
            onHoverEnd={() => setHovered(null)}
            onClick={() => handleSelect(sc)}
            whileHover={sc.status === 'live' ? { scale: 1.03, y: -4 } : {}}
            whileTap={sc.status === 'live' ? { scale: 0.98 } : {}}
          >
            {/* Portrait area */}
            <div className="sc-portrait" style={{ background: sc.portrait_bg }}>
              <span className="sc-icon">{ICONS[sc.id]}</span>
              <div className="sc-portrait-glow" style={{ '--glow': sc.color }} />
              {sc.status === 'live' && (
                <div className="sc-live-badge">
                  <span className="status-dot live" />
                  LIVE
                </div>
              )}
              {sc.status === 'coming_soon' && (
                <div className="sc-coming-badge">COMING SOON</div>
              )}
            </div>

            {/* Info */}
            <div className="sc-info">
              <h2 className="sc-name chalk-text" style={{ color: sc.color }}>{sc.name}</h2>
              <p className="sc-years">{sc.years}</p>
              <div className="sc-tags">
                <span className="tag tag-muted">{sc.era}</span>
                <span className="tag" style={{
                  background: `rgba(${hexToRgb(sc.color)},0.12)`,
                  color: sc.color,
                  border: `1px solid rgba(${hexToRgb(sc.color)},0.25)`
                }}>{sc.domain}</span>
              </div>
              <p className="sc-specialty">{sc.specialty}</p>
              <blockquote className="sc-quote">
                <span className="sc-quote-mark">"</span>
                {sc.tagline.replace(/^"|"$/g, '')}
                <span className="sc-quote-mark">"</span>
              </blockquote>

              {sc.status === 'live' && (
                <motion.div
                  className="sc-enter-btn"
                  animate={{ opacity: hovered === sc.id ? 1 : 0.7 }}
                >
                  Enter Classroom →
                </motion.div>
              )}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Footer */}
      <footer className="lobby-footer">
        <p>Every response is grounded in real historical documents. RAG-powered. Memory-persistent.</p>
      </footer>
    </div>
  )
}

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16)
  const g = parseInt(hex.slice(3,5),16)
  const b = parseInt(hex.slice(5,7),16)
  return `${r},${g},${b}`
}
