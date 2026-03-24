import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/camera/',
  build: {
    outDir: '../pioreactor_camera/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/camera/api': {
        target: 'http://100.110.27.52:8190',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/camera/, ''),
      },
      '/camera/images': {
        target: 'http://100.110.27.52:8190',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/camera/, ''),
      },
    },
  },
})
