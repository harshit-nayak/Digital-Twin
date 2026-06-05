import { Sidebar } from './components/Sidebar';
import { Classroom } from './components/Classroom';

export function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <Classroom />
    </div>
  );
}

