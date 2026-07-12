import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Tailwind dark mode via class is configured in index.css @import
  server: {
    proxy: {
      '/documents': 'http://localhost:8000',
      '/senders': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/monitor': {
        target: 'http://localhost:8000',
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // Disable buffering for SSE streams
            proxyRes.headers['x-accel-buffering'] = 'no'
          })
        },
      },
      '/chat': 'http://localhost:8000',
      '/config': 'http://localhost:8000',
      '/collections': 'http://localhost:8000',
      '/items': 'http://localhost:8000',
      '/contracts': 'http://localhost:8000',
      '/services': 'http://localhost:8000',
      '/tax': 'http://localhost:8000',
    },
  },
})
