import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ws': { target: 'ws://localhost:8000', ws: true },
      '/orders': 'http://localhost:8000',
      '/orderbook': 'http://localhost:8000',
      '/trades': 'http://localhost:8000',
      '/simulation': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ai': 'http://localhost:8000',
    },
  },
})
