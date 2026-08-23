import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  optimizeDeps: {
    include: ['utils'],
  },
  ssr: {
    noExternal: ['utils'],
  },
  build: {
    // Standard Rollup externalization
    rollupOptions: {
      external: ['ws'],
    },
    // Rolldown externalization
    rolldownOptions: {
      external: ['ws'],
    }
  }
})
