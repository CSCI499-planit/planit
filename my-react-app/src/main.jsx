import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { BrowserRouter } from "react-router-dom";
import './styles/index.css'
import './components/button.css'
import './components/destination.css'
import './components/navbar.css'
import './components/landing.css'
import './components/home.css'
import './components/profile.css'
import './components/signup.css'
import './components/survey.css'

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <App />
    </BrowserRouter>
  </StrictMode>
);
