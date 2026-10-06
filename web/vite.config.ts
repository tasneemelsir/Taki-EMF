import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// The built site goes straight into server/static, which the Python server serves.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  build: {
    outDir: path.resolve(__dirname, '../server/static'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 2500,
    rollupOptions: {
      output: {
        manualChunks: { plotly: ['plotly.js-cartesian-dist-min'], three: ['three'] },
      },
    },
  },
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000' } },
});
