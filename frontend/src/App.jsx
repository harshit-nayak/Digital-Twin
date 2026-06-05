import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { useStore } from './store'
import ScientistLobby from './pages/ScientistLobby'
import ChalkboardRoom from './pages/ChalkboardRoom'

export default function App() {
  const loadScientists = useStore(s => s.loadScientists)

  useEffect(() => {
    loadScientists()
  }, [loadScientists])

  return (
    <div className="app-root">
      <Routes>
        <Route path="/"               element={<ScientistLobby />} />
        <Route path="/room/:id"       element={<ChalkboardRoom />} />
        <Route path="*"               element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}
