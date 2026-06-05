import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStore } from '../store'
import SourceBadge from './SourceBadge'
import './ChatWindow.css'

// Typewriter component for streaming text
function TypewriterText({ text, isStreaming }) {
  return (
    <motion.span
      className={`chat-text chalk-text ${isStreaming ? 'streaming' : ''}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      {text}
      {isStreaming && <span className="cursor-blink">|</span>}
    </motion.span>
  )
}

// Individual message bubble
function Message({ msg, index }) {
  const isUser = msg.role === 'user'

  return (
    <motion.div
      className={`message-row ${isUser ? 'user' : 'assistant'}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
    >
      {!isUser && (
        <div className="msg-emotion-tag">
          {msg.emotion && (
            <span className={`emotion-label emotion-${msg.emotion}`}>
              {EMOTION_ICONS[msg.emotion] || '🧠'} {msg.emotion}
            </span>
          )}
          {msg.faithfulness != null && (
            <span className={`faithfulness-score ${msg.faithfulness > 0.7 ? 'good' : msg.faithfulness > 0.5 ? 'ok' : 'low'}`}
              title="Faithfulness: how grounded this response is in actual source text">
              ◈ {(msg.faithfulness * 100).toFixed(0)}%
            </span>
          )}
        </div>
      )}

      <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        {isUser ? (
          <span className="chalk-text user-text">{msg.text}</span>
        ) : (
          <TypewriterText text={msg.text} isStreaming={false} />
        )}
      </div>

      {/* Sources */}
      {!isUser && msg.sources?.length > 0 && (
        <div className="msg-sources">
          {msg.sources.map((src, i) => (
            <SourceBadge key={i} source={src} />
          ))}
        </div>
      )}

      {/* Rewritten query hint */}
      {!isUser && msg.rewritten && msg.rewritten !== msg.text && (
        <div className="msg-rewritten">
          <span className="rewritten-label">Searched for:</span>
          <span className="rewritten-text">"{msg.rewritten}"</span>
        </div>
      )}
    </motion.div>
  )
}

const EMOTION_ICONS = {
  EXCITED:       '✨',
  CONTEMPLATIVE: '💭',
  AMUSED:        '😄',
  SKEPTICAL:     '🤔',
  SAD:           '😔',
  NEUTRAL:       '🧠',
  PASSIONATE:    '🔥',
}

export default function ChatWindow() {
  const messages      = useStore(s => s.messages)
  const isLoading     = useStore(s => s.isLoading)
  const streamingText = useStore(s => s.streamingText)
  const scientist     = useStore(s => s.scientist)
  const timelineYear  = useStore(s => s.timelineYear)
  const bottomRef     = useRef(null)

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  return (
    <div className="chat-window">
      {/* Empty state */}
      {messages.length === 0 && !isLoading && (
        <motion.div
          className="chat-empty"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <div className="chat-empty-icon">⚛</div>
          <h2 className="chalk-text chat-empty-title">
            {scientist?.name || 'The Classroom'}
          </h2>
          {timelineYear && (
            <p className="chalk-text chat-empty-year">
              Year {timelineYear}
            </p>
          )}
          <p className="chat-empty-hint">
            Ask me anything within my domain of knowledge.
            Every answer traces to my actual writings.
          </p>
          <div className="chat-empty-prompts">
            {STARTER_PROMPTS.map((p, i) => (
              <StarterPrompt key={i} text={p} />
            ))}
          </div>
        </motion.div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        <AnimatePresence>
          {messages.map((msg, i) => (
            <Message key={i} msg={msg} index={i} />
          ))}
        </AnimatePresence>

        {/* Streaming in-progress */}
        {streamingText && (
          <motion.div
            className="message-row assistant"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="message-bubble assistant-bubble">
              <TypewriterText text={streamingText} isStreaming={true} />
            </div>
          </motion.div>
        )}

        {/* Loading indicator (no streaming text yet) */}
        {isLoading && !streamingText && (
          <motion.div
            className="message-row assistant"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="message-bubble assistant-bubble loading-bubble">
              <span className="thinking-dots">
                <span>.</span><span>.</span><span>.</span>
              </span>
              <span className="chalk-text thinking-text">thinking</span>
            </div>
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function StarterPrompt({ text }) {
  const sendMessage = useStore(s => s.sendMessage)
  return (
    <motion.button
      className="starter-prompt btn btn-chalk"
      onClick={() => sendMessage(text)}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      {text}
    </motion.button>
  )
}

const STARTER_PROMPTS = [
  'What is special relativity?',
  'Explain the photoelectric effect',
  'Why do you disagree with quantum mechanics?',
  'What was your greatest regret?',
]
