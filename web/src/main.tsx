import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './lib/install';        // listens for the browser's offer to install, which comes early
import './styles/app.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
