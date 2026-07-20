import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { CustomerProfileProvider } from './context/CustomerProfileContext.jsx'
import { LanguageProvider } from './context/LanguageContext.jsx'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <LanguageProvider>
      <CustomerProfileProvider>
        <App />
      </CustomerProfileProvider>
    </LanguageProvider>
  </React.StrictMode>,
)
