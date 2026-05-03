import React, { useState } from 'react'
import { Routes, Route, Outlet, Navigate } from 'react-router-dom'
import './styles/index.css'

import { AuthProvider, useAuth } from './context/AuthContext'
import LandingPage    from './pages/landing'
import SignupPage     from './pages/signup'
import SigninPage     from './pages/signin'
import SurveyPage     from './pages/survey'
import Navbar         from './pages/navbar'
import HomePage       from './pages/home'
import ProfilePage    from './pages/profile'
import DestinationPage from './pages/destination'

export const DarkModeContext = React.createContext()

function ProtectedRoute() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <Outlet /> : <Navigate to="/signin" replace />
}

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
    <AuthProvider>
      <Routes>
        <Route path="/"       element={<LandingPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/signin" element={<SigninPage />} />

        {/* survey is protected — user must be signed up before submitting preferences */}
        <Route element={<ProtectedRoute />}>
          <Route path="/survey" element={<SurveyPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route path="/app" element={<AppLayout />}>
            <Route index        element={<HomePage />} />
            <Route path="home"  element={<HomePage />} />
            <Route path="destination" element={<DestinationPage />} />
            <Route path="profile"     element={<ProfilePage />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  )
}
