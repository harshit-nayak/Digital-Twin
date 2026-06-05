import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat':      'http://localhost:8000',
      '/scientists':'http://localhost:8000',
      '/memory':    'http://localhost:8000',
      '/admin':     'http://localhost:8000',
    }
  }
})
