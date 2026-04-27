import React, { useState } from 'react'
import { Routes, Route, Outlet } from 'react-router-dom'
import './styles/index.css'
import LandingPage from './pages/landing'
import Navbar from './pages/navbar'
import HomePage from './pages/home'
import ProfilePage from './pages/profile'
import DestinationPage from './pages/destination'
import SignupPage from './pages/signup'
import SurveyPage from './pages/survey'

export const DarkModeContext = React.createContext()

function AppLayout() {
  const [darkMode, setDarkMode] = useState(false)

  return (
    <DarkModeContext.Provider value={{ darkMode, setDarkMode }}>
      <div className={darkMode ? 'dark-mode' : ''}>
        <Navbar />
        <Outlet />
      </div>
    </DarkModeContext.Provider>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/survey" element={<SurveyPage />} />
      <Route path="/app" element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="home" element={<HomePage />} />
        <Route path="destination" element={<DestinationPage />} />
        <Route path="profile" element={<ProfilePage />} />
      </Route>
    </Routes>
  )
}