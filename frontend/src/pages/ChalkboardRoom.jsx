import { useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store'
import MemorySidebar from '../components/MemorySidebar'
import ChatWindow from '../components/ChatWindow'
import InputBar from '../components/InputBar'
import TimelineSlider from '../components/TimelineSlider'
import EmotionAvatar from '../components/EmotionAvatar'
import ModeSelector from '../components/ModeSelector'
import './ChalkboardRoom.css'

// Timeline milestones for Einstein
const EINSTEIN_MILESTONES = [
  { year: 1905, label: 'Annus Mirabilis', desc: 'Photoelectric effect, special relativity, E=mc²' },
  { year: 1915, label: 'General Relativity', desc: 'Field equations complete. Gravity as curved spacetime.' },
  { year: 1921, label: 'Nobel Prize', desc: 'Awarded for photoelectric effect, not relativity.' },
  { year: 1927, label: 'Solvay Conference', desc: 'Debates Bohr. "God does not play dice."' },
  { year: 1933, label: 'Princeton Years', desc: 'Fled Germany. Institute for Advanced Study.' },
  { year: 1949, label: 'Late Work', desc: 'Unified field theory. Declining health.' },
  { year: 1955, label: 'Final Year', desc: 'Last letter to Russell. Aortic aneurysm.' },
]

const MILESTONES_BY_ID = { einstein: EINSTEIN_MILESTONES }

export default function ChalkboardRoom() {
  const { id } = useParams()
  const navigate = useNavigate()

  const scientist     = useStore(s => s.scientist)
  const setScientist  = useStore(s => s.setScientist)
  const timelineYear  = useStore(s => s.timelineYear)
  const setTimelineYear = useStore(s => s.setTimelineYear)
  const scientists    = useStore(s => s.scientists)
  const loadMemories  = useStore(s => s.loadMemories)
  const currentEmotion = useStore(s => s.currentEmotion)

  // If we arrived via direct URL, restore scientist from API data
  useEffect(() => {
    if (!scientist && scientists.length) {
      const found = scientists.find(s => s.id === id)
      if (found) {
        setScientist(found)
        setTimelineYear(1927)
      } else {
        navigate('/')
      }
    } else if (!scientist && id === 'einstein') {
      // Fallback: create minimal Einstein object
      setScientist({ id: 'einstein', name: 'Albert Einstein' })
      setTimelineYear(1927)
    }
  }, [id, scientist, scientists, setScientist, setTimelineYear, navigate])

  useEffect(() => {
    if (scientist) loadMemories()
  }, [scientist, loadMemories])

  const milestones = MILESTONES_BY_ID[id] || []

  if (!scientist) {
    return (
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' }}>
        <span className="spinner" />
      </div>
    )
  }

  return (
    <div className="room-root">

      {/* Left Sidebar — Memory / Profile / Corpus */}
      <aside className="room-sidebar">
        <MemorySidebar />
      </aside>

      {/* Main Chalkboard Area */}
      <main className="room-main">

        {/* Top Bar */}
        <div className="room-topbar">
          <button className="btn btn-ghost room-back" onClick={() => navigate('/')}>
            ← Lobby
          </button>

          <div className="room-scientist-id">
            <span className="room-scientist-name chalk-text">{scientist.name}</span>
            <span className="room-divider">·</span>
            <ModeSelector />
          </div>

          <div className="room-timeline-area">
            <TimelineSlider milestones={milestones} />
          </div>
        </div>

        {/* Chat */}
        <ChatWindow />

        {/* Input */}
        <InputBar />
      </main>

      {/* Right Panel — Emotion Avatar */}
      <aside className="room-right-panel">
        <EmotionAvatar emotion={currentEmotion} scientistId={id} />
      </aside>

    </div>
  )
}
