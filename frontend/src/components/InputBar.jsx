import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useStore } from '../store'
import './InputBar.css'

export default function InputBar() {
  const [text, setText]       = useState('')
  const [isRecording, setIsRec] = useState(false)
  const sendMessage = useStore(s => s.sendMessage)
  const isLoading   = useStore(s => s.isLoading)
  const textareaRef = useRef(null)
  const recognitionRef = useRef(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 140) + 'px'
  }, [text])

  const handleSend = () => {
    const q = text.trim()
    if (!q || isLoading) return
    sendMessage(q)
    setText('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleVoice = () => {
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      alert('Voice input not supported in this browser.')
      return
    }
    if (isRecording) {
      recognitionRef.current?.stop()
      setIsRec(false)
      return
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'en-US'
    rec.continuous = false
    rec.interimResults = true
    rec.onresult = (e) => {
      const transcript = Array.from(e.results)
        .map(r => r[0].transcript).join('')
      setText(transcript)
    }
    rec.onend = () => setIsRec(false)
    rec.start()
    recognitionRef.current = rec
    setIsRec(true)
  }

  return (
    <div className="input-bar-wrap">
      <div className="input-bar">
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          id="chat-input"
          className="input-textarea chalk-text"
          placeholder="Ask Einstein anything..."
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          disabled={isLoading}
          rows={1}
        />

        {/* Actions */}
        <div className="input-actions">
          {/* Voice button */}
          <motion.button
            id="voice-btn"
            className={`input-btn voice-btn ${isRecording ? 'recording' : ''}`}
            onClick={toggleVoice}
            title={isRecording ? 'Stop recording' : 'Voice input'}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            {isRecording ? '⏹' : '🎤'}
          </motion.button>

          {/* Send button */}
          <motion.button
            id="send-btn"
            className="input-btn send-btn btn btn-accent"
            onClick={handleSend}
            disabled={!text.trim() || isLoading}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            {isLoading ? <span className="spinner" style={{width:14,height:14}} /> : '↵'}
          </motion.button>
        </div>
      </div>
      <p className="input-hint">Enter to send · Shift+Enter for new line · 🎤 for voice</p>
    </div>
  )
}
