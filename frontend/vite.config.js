import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()], base: '/project-1/', optimizeDeps: { exclude: ['maplibre-gl'] }, server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
