import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

export default function LandingPage() {
  const navigate = useNavigate()
  const globeRef = useRef(null)

  useEffect(() => {
    const globe = globeRef.current
    let frame
    const animate = (ts) => {
      globe.style.transform = `
        translateY(${Math.sin(ts / 4000) * 6}px)
        translateX(${Math.cos(ts / 5000) * 4}px)
      `
      frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [])

  return (
    <section className="hero">
      <div className="hero__content">
        <h1 className="hero__headline">
          Your next trip,<br />
          <em>planned in seconds!</em>
        </h1>
        <p className="hero__sub">Not hours.</p>
        <p className="hero__body">
          PlanIt turns your interests, budget, and dates into a complete day-by-day
          itinerary automatically. No more tab-hopping, no more guesswork.
        </p>
        <div className="hero__ctas">
          <button className="btn btn--primary" onClick={() => navigate('/signup')}>Start Planning for Free!</button>
          <button className="btn btn--secondary">Learn More</button>
        </div>
        <div className="hero__stats">
          <div className="stat"><span className="stat__value">Free</span><span className="stat__label">For everyone</span></div>
          <div className="stat"><span className="stat__value">100%</span><span className="stat__label">Tailored to you</span></div>
          <div className="stat"><span className="stat__value">67k</span><span className="stat__label">Users in NY (and growing)</span></div>
        </div>
      </div>

      <div className="hero__globe-wrap">
        <div className="hero__globe" ref={globeRef}>
          <img
            src="https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/The_Earth_seen_from_Apollo_17.jpg/1024px-The_Earth_seen_from_Apollo_17.jpg"
            alt="Earth"
            className="hero__globe-img"
          />
          <div className="hero__globe-glow" />
        </div>
      </div>
    </section>
  )
}