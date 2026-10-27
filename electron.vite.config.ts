import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

// Main bundles its dependencies too, so the packaged app ships only out/ and no node_modules.
export default defineConfig({
  main: { build: { externalizeDeps: false } },
  preload: {},
  renderer: {
    plugins: [react()]
  }
})
