import { useEffect, useState } from 'react'
import { api } from '../api/client'
import '../components/generate.css'

function PriceLevel({ level }) {
  if (!level) return null

  return (
    <span className="stop-price">
      {['$', '$', '$', '$'].map((s, i) => (
        <span
          key={i}
          className={i < level ? 'price-sign filled' : 'price-sign'}
        >
          {s}
        </span>
      ))}
    </span>
  )
}

function PlaceCard({
  place,
  feedback,
  onLike,
  onDislike,
}) {
  const displayAddr =
    [
      place.street,
      place.suburb || place.district,
      place.city,
      place.state,
    ]
      .filter(Boolean)
      .slice(0, 3)
      .join(', ') ||
    place.address?.split(',').slice(0, 3).join(',')

  return (
    <div className="stop-card">

      <div className="stop-card__top">
        <div>
          <div className="stop-card__name">
            {place.name}
          </div>

          <div className="stop-card__meta">
            <PriceLevel level={place.price_level} />
          </div>
        </div>
      </div>

      {displayAddr && (
        <div className="stop-card__address">
          {displayAddr}
        </div>
      )}

      {place.tags?.length > 0 && (
        <div className="stop-card__tags">
          {place.tags.map(tag => (
            <span key={tag} className="stop-tag">
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="day-card__actions">

        <button
          className={`feedback-btn feedback-btn--like ${
            feedback === 'like' ? 'active' : ''
          }`}
          onClick={onLike}
          disabled={!!feedback}
        >
          Like
        </button>

        <button
          className={`feedback-btn feedback-btn--dislike ${
            feedback === 'dislike' ? 'active' : ''
          }`}
          onClick={onDislike}
          disabled={!!feedback}
        >
          Dislike
        </button>

      </div>
    </div>
  )
}

export default function GeneratePlacesPage() {
  const [location, setLocation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [places, setPlaces] = useState([])
  const [toast, setToast] = useState('')
  const [feedback, setFeedback] = useState({})

  useEffect(() => {
    const handleMouseMove = e => {
      const x = (e.clientX / window.innerWidth) * 100
      const y = (e.clientY / window.innerHeight) * 100
      const el = document.querySelector('.generate-page')
      if (!el) return
      el.style.setProperty('--x', `${x}%`)
      el.style.setProperty('--y', `${y}%`)
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY
      const max = document.body.scrollHeight - window.innerHeight
      const progress = max > 0 ? scrollY / max : 0
      const hue = 200 + progress * 100

      const el = document.querySelector('.generate-page')
      if (!el) return
      el.style.setProperty('--hue', hue)
    }

    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const showToast = msg => {
    setToast(msg)
    setTimeout(() => setToast(''), 2800)
  }

  const handleSubmit = e => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setPlaces([])

    setTimeout(() => {
      setPlaces([
        {
          id: Date.now(),
          name: 'Testing',
          city: 'Brooklyn',
          state: 'NY',
          address: 'Testing',
          price_level: 2,
          tags: ['cafe', 'coffee'],
        },
      ])
      setLoading(false)
    }, 900)
  }

  const handleFeedback = (place, type) => {
    if (feedback[place.id]) return

    setFeedback(prev => ({ ...prev, [place.id]: type }))
    showToast(type === 'like' ? 'Liked!' : 'Feedback noted!')
  }

  return (
    <div className="generate-page">
      <div className="generate-container">

        <h1>Discover <em>Places.</em></h1>

        <p className="generate-subtitle">
          Find places tailored to your destination.
        </p>

        {/* INSTRUCTIONS ADDED BACK */}
        <div className="generate-instructions">
          <p>How it works:</p>
          <ul>
            <li>
              Enter any city, neighborhood, or destination.
            </li>
            <li>
              Save places you like to access them later from your home page.
            </li>
            <li>
              Open places directly in Google Maps for directions and exploration.
            </li>
          </ul>
        </div>

        <form onSubmit={handleSubmit} className="generate-form">
          <div className="form-group">
            <label>Destination</label>
            <input
              type="text"
              placeholder="e.g., Brooklyn, New York"
              value={location}
              onChange={e => setLocation(e.target.value)}
              required
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button
            type="submit"
            className="btn btn--primary"
            disabled={loading}
          >
            {loading ? 'Finding places…' : 'Discover Places'}
          </button>
        </form>

        {places.length > 0 && (
          <div className="itinerary-result">

            <div className="itinerary-header">
              <h2>
                Places in <span>{location}</span>
              </h2>
            </div>

            <div className="places-grid">
              {places.map(place => (
                <PlaceCard
                  key={place.id}
                  place={place}
                  feedback={feedback[place.id]}
                  onLike={() => handleFeedback(place, 'like')}
                  onDislike={() => handleFeedback(place, 'dislike')}
                />
              ))}
            </div>

          </div>
        )}

      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}