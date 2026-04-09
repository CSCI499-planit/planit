import { Routes, Route } from 'react-router-dom'
import './App.css'
import LandingPage from './pages/landing'
import Navbar from './pages/navbar'
import HomePage from './pages/home'
import ProfilePage from './pages/profile'
import DestinationPage from './pages/destination'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/app"
        element={
          <>
            <Navbar />
            <Routes>
              <Route index element={<HomePage />} />
              <Route path="home" element={<HomePage />} />
              <Route path="destination" element={<DestinationPage />} />
              <Route path="profile" element={<ProfilePage />} />
            </Routes>
          </>
        }
      />
    </Routes>
  )
}