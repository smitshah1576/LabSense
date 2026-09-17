import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ThemeProvider } from './context/ThemeContext'
import { FeedbackProvider } from './components/ui/Feedback'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <FeedbackProvider>
          <App />
        </FeedbackProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
)
