import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store'
import './TimelineSlider.css'

export default function TimelineSlider({ milestones }) {
  const timelineYear    = useStore(s => s.timelineYear)
  const setTimelineYear = useStore(s => s.setTimelineYear)

  if (!milestones?.length) return null

  const activeIdx = milestones.findIndex(m => m.year === timelineYear)
  const active    = milestones[activeIdx] ?? milestones[milestones.length - 1]

  return (
    <div className="timeline-wrap">
      {/* Active milestone info */}
      <div className="timeline-info">
        <span className="timeline-year chalk-text">{active?.year}</span>
        <span className="timeline-label">{active?.label}</span>
      </div>

      {/* Milestone dots */}
      <div className="timeline-track">
        <div className="timeline-line" />
        {milestones.map((m, i) => {
          const isActive  = m.year === timelineYear
          const isPast    = m.year <= (timelineYear || 0)
          return (
            <motion.button
              key={m.year}
              id={`timeline-${m.year}`}
              className={`timeline-dot ${isActive ? 'active' : ''} ${isPast ? 'past' : ''}`}
              onClick={() => setTimelineYear(m.year)}
              title={`${m.year}: ${m.label}\n${m.desc}`}
              whileHover={{ scale: 1.4 }}
              whileTap={{ scale: 0.9 }}
            >
              {isActive && (
                <motion.div
                  className="dot-ring"
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  layoutId="active-ring"
                />
              )}
            </motion.button>
          )
        })}
      </div>

      {/* Tooltip for active milestone */}
      <div className="timeline-desc">{active?.desc}</div>
    </div>
  )
}
