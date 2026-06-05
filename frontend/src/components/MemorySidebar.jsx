import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store'
import './MemorySidebar.css'

const TABS = [
  { id: 'profile',  label: 'Profile',  icon: '👤' },
  { id: 'memories', label: 'Memories', icon: '🧠' },
  { id: 'corpus',   label: 'Sources',  icon: '📚' },
]

const MEMORY_TYPE_COLORS = {
  identity:   '#d4a843',
  goal:       '#7ab87a',
  topic:      '#a8c4e0',
  episode:    '#e8a0a0',
  preference: '#c0a8e8',
}

export default function MemorySidebar() {
  const sidebarTab  = useStore(s => s.sidebarTab)
  const setSidebarTab = useStore(s => s.setSidebarTab)
  const scientist   = useStore(s => s.scientist)
  const memories    = useStore(s => s.memories)
  const userProfile = useStore(s => s.userProfile)
  const lastSources = useStore(s => s.lastSources)
  const deleteMemory = useStore(s => s.deleteMemory)
  const clearMemories = useStore(s => s.clearMemories)
  const timelineYear = useStore(s => s.timelineYear)

  return (
    <div className="sidebar-root">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-scientist-badge">
          <span className="sidebar-icon">⚛</span>
          <div>
            <p className="sidebar-scientist-name chalk-text">{scientist?.name || 'Scientist'}</p>
            {timelineYear && <p className="sidebar-year">Year {timelineYear}</p>}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="sidebar-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            id={`sidebar-tab-${tab.id}`}
            className={`sidebar-tab-btn ${sidebarTab === tab.id ? 'active' : ''}`}
            onClick={() => setSidebarTab(tab.id)}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="sidebar-content">
        <AnimatePresence mode="wait">
          {sidebarTab === 'profile' && (
            <motion.div
              key="profile"
              className="tab-panel"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
            >
              <ProfileTab profile={userProfile} memories={memories} />
            </motion.div>
          )}
          {sidebarTab === 'memories' && (
            <motion.div
              key="memories"
              className="tab-panel"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
            >
              <MemoriesTab memories={memories} onDelete={deleteMemory} onClear={clearMemories} />
            </motion.div>
          )}
          {sidebarTab === 'corpus' && (
            <motion.div
              key="corpus"
              className="tab-panel"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
            >
              <SourcesTab sources={lastSources} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ── Profile Tab ─────────────────────────────────────────────────

function ProfileTab({ profile, memories }) {
  const messages       = useStore(s => s.messages)
  const topicMemories  = memories.filter(m => m.memory_type === 'topic')
  const identityMems   = memories.filter(m => m.memory_type === 'identity')
  const preferMems     = memories.filter(m => m.memory_type === 'preference')

  return (
    <div className="profile-tab">
      <div className="profile-section">
        <h3 className="section-title">Session Info</h3>
        <div className="profile-stat">
          <span className="stat-label">Messages</span>
          <span className="stat-value">{messages.length}</span>
        </div>
        <div className="profile-stat">
          <span className="stat-label">Memories stored</span>
          <span className="stat-value">{memories.length}</span>
        </div>
      </div>

      {identityMems.length > 0 && (
        <div className="profile-section">
          <h3 className="section-title">About You</h3>
          {identityMems.map(m => (
            <div key={m.id} className="profile-fact">
              <span className="fact-text">{m.content}</span>
            </div>
          ))}
        </div>
      )}

      {topicMemories.length > 0 && (
        <div className="profile-section">
          <h3 className="section-title">Topics Explored</h3>
          <div className="topics-grid">
            {topicMemories.slice(0, 8).map(m => (
              <span key={m.id} className="topic-chip">{m.content.slice(0, 30)}</span>
            ))}
          </div>
        </div>
      )}

      {preferMems.length > 0 && (
        <div className="profile-section">
          <h3 className="section-title">Your Learning Style</h3>
          {preferMems.map(m => (
            <div key={m.id} className="profile-fact">
              <span className="fact-text">{m.content}</span>
            </div>
          ))}
        </div>
      )}

      {memories.length === 0 && (
        <div className="empty-state">
          <p>Start a conversation and I'll begin building your learning profile.</p>
        </div>
      )}
    </div>
  )
}

// ── Memories Tab ─────────────────────────────────────────────────

function MemoriesTab({ memories, onDelete, onClear }) {
  return (
    <div className="memories-tab">
      {memories.length > 0 && (
        <div className="memories-header">
          <span className="memories-count">{memories.length} memories</span>
          <button
            className="btn btn-ghost clear-btn"
            onClick={() => { if(confirm('Clear all memories for this scientist?')) onClear() }}
          >
            Clear all
          </button>
        </div>
      )}

      {memories.length === 0 && (
        <div className="empty-state">
          <p>No memories yet. Chat with Einstein and he'll start remembering things about you.</p>
        </div>
      )}

      <div className="memories-list">
        <AnimatePresence>
          {memories.map(m => (
            <motion.div
              key={m.id}
              className="memory-item"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div className="memory-top">
                <span
                  className="memory-type-badge"
                  style={{
                    background: (MEMORY_TYPE_COLORS[m.memory_type] || '#888') + '22',
                    color: MEMORY_TYPE_COLORS[m.memory_type] || '#888',
                    borderColor: (MEMORY_TYPE_COLORS[m.memory_type] || '#888') + '44',
                  }}
                >
                  {m.memory_type}
                </span>
                <div className="memory-importance-wrap">
                  <div className="importance-bar" style={{ width: 48 }}>
                    <div className="importance-fill" style={{ width: `${(m.importance || 0.5) * 100}%` }} />
                  </div>
                  <span className="importance-num">{(m.importance || 0.5).toFixed(2)}</span>
                </div>
                <button
                  className="memory-delete-btn"
                  onClick={() => onDelete(m.id)}
                  title="Delete this memory"
                >×</button>
              </div>
              <p className="memory-content">{m.content}</p>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}

// ── Sources Tab ──────────────────────────────────────────────────

function SourcesTab({ sources }) {
  if (!sources?.length) {
    return (
      <div className="empty-state">
        <p>Sources from Einstein's corpus will appear here after each response.</p>
      </div>
    )
  }

  return (
    <div className="sources-tab">
      <p className="sources-header-text">Last response drawn from:</p>
      {sources.map((src, i) => (
        <div key={i} className="source-item">
          <div className="source-icon">📄</div>
          <div className="source-detail">
            <p className="source-title">{src.title || src.source_title || 'Unknown source'}</p>
            {src.year && <p className="source-year">{src.year} · {src.type || src.source_type || ''}</p>}
          </div>
        </div>
      ))}
    </div>
  )
}
