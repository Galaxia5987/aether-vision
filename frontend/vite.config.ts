import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// During `npm run dev`, API calls are proxied to the Python backend.
const backend = process.env.AETHER_VISION_BACKEND ?? 'http://127.0.0.1:5803'

export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': { target: backend, ws: true, changeOrigin: true },
    },
  },
})
