import { FormEvent, useState } from 'react';
import { motion } from 'framer-motion';
import { Send, Sparkles } from 'lucide-react';
import { chat } from '../services/chat';
import { useClassroom } from '../store/classroom';

export function Classroom() {
  const { scientist, timeline, sessionId, messages, addMessage } = useClassroom();
  const [input, setInput] = useState('Explain the physics of light and motion.');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message || loading) return;

    setError('');
    setInput('');
    addMessage({ role: 'student', text: message });
    setLoading(true);
    try {
      const response = await chat({ session_id: sessionId, scientist, timeline, message });
      addMessage({ role: 'scientist', text: response.message, response });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Chat failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="classroom">
      <header className="topbar">
        <div>
          <p>{scientist}</p>
          <h1>Scientist Classroom</h1>
        </div>
        <div className="avatar" aria-label={`${scientist} avatar`}>
          <Sparkles size={22} />
        </div>
      </header>

      <section className="chalkboard">
        {messages.length === 0 ? (
          <div className="empty-state">
            <h2>Ask a grounded science question.</h2>
            <p>The first response uses REST chat; streaming can attach to the same service contract later.</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <motion.article
              className={`message ${message.role}`}
              key={`${message.role}-${index}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="message-role">{message.role === 'student' ? 'You' : scientist}</div>
              <p>{message.text}</p>
              {message.response?.sources.length ? (
                <div className="sources">
                  {message.response.sources.map((source) => (
                    <details key={source.id}>
                      <summary>{source.title}</summary>
                      <p>{source.excerpt}</p>
                    </details>
                  ))}
                </div>
              ) : null}
            </motion.article>
          ))
        )}
      </section>

      <form className="composer" onSubmit={submit}>
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask the scientist..." />
        <button type="submit" disabled={loading} title="Send">
          <Send size={18} />
        </button>
      </form>
      {error ? <div className="error">{error}</div> : null}
    </main>
  );
}

