import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/documents': 'http://localhost:8000',
      '/senders': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/monitor': 'http://localhost:8000',
    },
  },
})
