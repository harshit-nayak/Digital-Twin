import { Atom, BookOpen, Clock, UserRound } from 'lucide-react';
import { useClassroom, type ScientistId } from '../store/classroom';

const scientists: { id: ScientistId; label: string; timeline: string }[] = [
  { id: 'einstein', label: 'Einstein', timeline: '1905' },
  { id: 'newton', label: 'Newton', timeline: '1687' },
  { id: 'feynman', label: 'Feynman', timeline: '1965' },
  { id: 'tesla', label: 'Tesla', timeline: '1891' },
  { id: 'curie', label: 'Curie', timeline: '1911' }
];

export function Sidebar() {
  const { scientist, setScientist, setTimeline, timeline } = useClassroom();

  return (
    <aside className="sidebar">
      <div className="brand">
        <Atom size={22} />
        <span>AIMS Classroom</span>
      </div>

      <section>
        <div className="section-title">
          <UserRound size={16} />
          Scientist
        </div>
        <div className="scientist-list">
          {scientists.map((item) => (
            <button
              className={item.id === scientist ? 'active' : ''}
              key={item.id}
              onClick={() => {
                setScientist(item.id);
                setTimeline(item.timeline);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      <section>
        <label className="section-title" htmlFor="timeline">
          <Clock size={16} />
          Timeline
        </label>
        <input id="timeline" value={timeline} onChange={(event) => setTimeline(event.target.value)} />
      </section>

      <section className="source-note">
        <BookOpen size={16} />
        <span>Sources appear after each grounded answer.</span>
      </section>
    </aside>
  );
}

