import { useState, useEffect } from "react";
import { Routes, Route, Outlet, Navigate } from "react-router-dom";
import "./styles/index.css";

import { AuthProvider, useAuth } from "./context/AuthContext";
import LandingPage from "./pages/landing";
import SignupPage from "./pages/signup";
import SigninPage from "./pages/signin";
import SurveyPage from "./pages/survey";
import UploadPage from "./pages/upload";
import Navbar from "./pages/navbar";
import HomePage from "./pages/home";
import ProfilePage from "./pages/profile";
import DestinationPage from "./pages/destination";
import GenerateItinerary from "./pages/generate-itinerary";
import GeneratePlaces from "./pages/generate-places";
import { DarkModeContext } from "./context/DarkModeContext";

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Outlet /> : <Navigate to="/signin" replace />;
}

function AppLayout() {
  const [darkMode, setDarkMode] = useState(false);

  return (
    <DarkModeContext.Provider value={{ darkMode, setDarkMode }}>
      <div
        className={darkMode ? "dark-mode" : ""}
        style={{ background: "#ffffffff", minHeight: "100vh" }}
      >
        <Navbar />
        <Outlet />
      </div>
    </DarkModeContext.Provider>
  );
}

function WakeServices() {
  useEffect(() => {
    fetch(import.meta.env.VITE_API_BASE_URL + "/wake").catch(() => {});
  }, []);
  return null;
}

export default function App() {
  return (
    <AuthProvider>
      <WakeServices />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/signin" element={<SigninPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/survey" element={<SurveyPage />} />
          <Route path="/upload" element={<UploadPage />} />
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route path="/app" element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="home" element={<HomePage />} />
            <Route path="generate-itinerary" element={<GenerateItinerary />} />
            <Route path="generate-places" element={<GeneratePlaces />} />
            <Route path="destination" element={<DestinationPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
