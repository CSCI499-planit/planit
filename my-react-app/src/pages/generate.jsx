import { useState } from 'react'
import { api } from '../api/client'
import { userStorage } from '../utils/userStorage'
import '../components/generate.css'

function formatTime(t) {
  if (!t) return null
  const [h, m] = t.split(':').map(Number)
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h >= 12 ? 'PM' : 'AM'}`
}

function Stars({ rating, reviewCount }) {
  if (!rating && !reviewCount) return <span className="stop-no-rating">No rating yet</span>
  const stars = rating ? Math.round(rating) : 0
  return (
    <span className="stop-stars">
      {[1,2,3,4,5].map(i => (
        <span key={i} className={i <= stars ? 'star filled' : 'star'}>{i <= stars ? '★' : '☆'}</span>
      ))}
      {rating && <span className="stop-rating-val">{rating.toFixed(1)}</span>}
      {reviewCount && <span className="stop-review-count">({reviewCount.toLocaleString()})</span>}
    </span>
  )
}

function PriceLevel({ level }) {
  if (!level) return null
  return (
    <span className="stop-price">
      {['$','$','$','$'].map((s, i) => (
        <span key={i} className={i < level ? 'price-sign filled' : 'price-sign'}>{s}</span>
      ))}
    </span>
  )
}

function StopCard({ stop }) {
  const { place, arrival_time, departure_time, travel_to_next } = stop
  const timeStr = arrival_time && departure_time
    ? `${formatTime(arrival_time)} – ${formatTime(departure_time)}`
    : arrival_time ? formatTime(arrival_time) : null

  const displayAddr = [place.street, place.suburb || place.district, place.city, place.state]
    .filter(Boolean).slice(0, 3).join(', ') || place.address?.split(',').slice(0,3).join(',')

  return (
    <div className="stop-item">
      <div className="stop-dot" />
      <div className="stop-card">
        <div className="stop-card__top">
          <span className="stop-card__name">{place.name}</span>
          {timeStr && <span className="stop-card__time">{timeStr}</span>}
        </div>
        <div className="stop-card__meta-row">
          <Stars rating={place.rating} reviewCount={place.review_count} />
          <PriceLevel level={place.price_level} />
        </div>
        {displayAddr && <div className="stop-card__address">{displayAddr}</div>}
        {place.tags?.length > 0 && (
          <div className="stop-card__tags">
            {place.tags.map(tag => <span key={tag} className="stop-tag">{tag}</span>)}
          </div>
        )}
        {travel_to_next && (
          <div className="stop-card__travel">{travel_to_next.duration_minutes} min to next stop</div>
        )}
      </div>
    </div>
  )
}

function DayCard({ dayData }) {
  const ordinals = ['','First','Second','Third','Fourth','Fifth','Sixth','Seventh']
  return (
    <div className="day-card">
      <div className="day-card__label">
        <div className="day-card__num">{dayData.day}</div>
        <span className="day-card__title">{ordinals[dayData.day] || `Day ${dayData.day}`} Day</span>
        {dayData.date && <span className="day-card__date">{dayData.date}</span>}
      </div>
      <div className="stops-timeline">
        {dayData.stops.map((stop, i) => <StopCard key={i} stop={stop} />)}
      </div>
    </div>
  )
}

export default function GeneratePage() {
  const [location, setLocation] = useState('')
  const [tripDays, setTripDays] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [itinerary, setItinerary] = useState(null)
  const [saved, setSaved] = useState(false)
  const [toast, setToast] = useState('')

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(''), 2800) }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true); setSaved(false); setItinerary(null)
    try {
      const data = await api.post('/recommend/itinerary', { location, trip_days: tripDays, top_k: 20, radius_m: 5000, limit: 50 })
      setItinerary(data.itinerary)
    } catch (err) {
      setError(err.message || 'Failed to generate itinerary')
    } finally { setLoading(false) }
  }

  const handleSave = () => {
    if (!itinerary) return
    const existing = userStorage.get('savedItineraries') || []
    userStorage.set('savedItineraries', [{ id: Date.now(), location, tripDays, savedAt: new Date().toLocaleDateString(), itinerary }, ...existing])
    setSaved(true)
    showToast('Itinerary saved to your home page!')
  }

  return (
    <div className="generate-page">
      <div className="generate-container">
        <h1>Plan your trip, <em>instantly.</em></h1>
        <p className="generate-subtitle">Enter a location and we'll build your perfect day-by-day itinerary.</p>
        <form onSubmit={handleSubmit} className="generate-form">
          <div className="form-group">
            <label htmlFor="location">Destination</label>
            <input id="location" type="text" placeholder="e.g., Brooklyn, New York" value={location} onChange={e => setLocation(e.target.value)} required />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="trip_days">Duration (days)</label>
              <input id="trip_days" type="number" min="1" max="7" value={tripDays} onChange={e => setTripDays(parseInt(e.target.value))} />
            </div>
          </div>
          {error && <div className="error-message">{error}</div>}
          <button type="submit" className="btn btn--primary" disabled={loading}>
            {loading ? 'Building your itinerary…' : 'Generate Itinerary'}
          </button>
        </form>
        {itinerary && (
          <div className="itinerary-result">
            <div className="itinerary-header">
              <h2>Your trip to <span>{location}</span></h2>
              <button className={`save-btn ${saved ? 'saved' : ''}`} onClick={handleSave} disabled={saved}>
                {saved ? 'Saved!' : 'Save Itinerary'}
              </button>
            </div>
            {itinerary.length === 0
              ? <div className="empty-itinerary">No stops found. Try a different destination!</div>
              : itinerary.map(day => <DayCard key={day.day} dayData={day} />)
            }
          </div>
        )}
      </div>
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}