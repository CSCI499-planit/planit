import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { userStorage } from '../utils/userStorage'
import '../components/generate.css'

const PLACES_PER_PAGE = 10

function getPlaceId(place) {
  return (
    place.place_id ||
    place.id ||
    `${place.name}-${place.latitude}-${place.longitude}`
  )
}

function getLocationKey(location) {
  return location.trim().toLowerCase().replace(/\s+/g, ' ')
}

function getShownPlaceIds(location) {
  const shownByLocation = userStorage.get('shownGeneratedPlaces') || {}
  return shownByLocation[getLocationKey(location)] || []
}

function rememberShownPlaces(location, nextPlaces) {
  const key = getLocationKey(location)
  const shownByLocation = userStorage.get('shownGeneratedPlaces') || {}
  const existing = shownByLocation[key] || []
  const nextIds = nextPlaces.map(getPlaceId).filter(Boolean)

  userStorage.set('shownGeneratedPlaces', {
    ...shownByLocation,
    [key]: [...new Set([...existing, ...nextIds])].slice(-250),
  })
}

function getDisplayAddress(place) {
  return (
    [
      place.street,
      place.suburb || place.district,
      place.city,
      place.state,
    ]
      .filter(Boolean)
      .slice(0, 3)
      .join(', ') ||
    place.address?.split(',').slice(0, 3).join(',') ||
    ''
  )
}

function getPlaceLocationLabel(place, locationQuery) {
  return (
    [place.city, place.state || place.country]
      .filter(Boolean)
      .join(', ') ||
    place.address ||
    locationQuery
  )
}

function toLikedDestination(place, locationQuery) {
  return {
    id: getPlaceId(place),
    name: place.name || 'Unnamed place',
    country: getPlaceLocationLabel(place, locationQuery),
    locationQuery,
    source: 'generated_place',
    place_id: place.place_id,
    city: place.city,
    state: place.state,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    rating: place.rating,
    tags: place.tags || place.categories || [],
  }
}

function openPlaceInGoogleMaps(place) {
  const query = [
    place.name,
    getDisplayAddress(place),
    place.city,
    place.state,
  ]
    .filter(Boolean)
    .join(', ') || (
    place.latitude && place.longitude
      ? `${place.latitude},${place.longitude}`
      : ''
  )

  if (!query) return

  window.open(
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`,
    '_blank'
  )
}

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
  const displayAddr = getDisplayAddress(place)

  return (
    <div className="stop-card place-card">

      <div className="stop-card__top">
        <div>
          <div className="stop-card__name">
            {place.name}
          </div>

          <div className="stop-card__meta">
            <PriceLevel level={place.price_level} />
          </div>
        </div>

      <div className="stop-card__actions">

        <button
          className="gmaps-btn"
          onClick={() => openPlaceInGoogleMaps(place)}
        >
          Open in Google Maps
        </button>

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

  const handleSubmit = async e => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setPlaces([])
    setFeedback({})

    try {
      const localExcluded = getShownPlaceIds(location)
      const data = await api.post('/recommend/places', {
        location,
        top_k: PLACES_PER_PAGE,
        radius_m: 5000,
        limit: 100,
        excluded_place_ids: localExcluded,
      })

      const seen = new Set(localExcluded)
      const nextPlaces = (data.places || [])
        .filter(place => {
          const placeId = getPlaceId(place)
          if (!placeId || seen.has(placeId)) return false
          seen.add(placeId)
          return true
        })
        .slice(0, PLACES_PER_PAGE)

      setPlaces(nextPlaces)
      rememberShownPlaces(location, nextPlaces)

      if (nextPlaces.length === 0) {
        setError('No new places found. Try a nearby neighborhood or a wider destination.')
      }
    } catch (err) {
      setError(err.message || 'Failed to discover places')
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async (place, type) => {
    const placeId = getPlaceId(place)

    if (feedback[placeId]) return

    try {
      await api.post('/interactions/', {
        place_id: placeId,
        event_type: type === 'like' ? 'like' : 'unlike',
      })
    } catch {
      showToast("Couldn't save feedback. Try again.")
      return
    }

    setFeedback(prev => ({ ...prev, [placeId]: type }))
    rememberShownPlaces(location, [place])

    if (type === 'like') {
      const likedPlace = toLikedDestination(place, location)
      const existing = userStorage.get('likedPlaces') || []
      const withoutDuplicate = existing.filter(
        dest => dest.id !== likedPlace.id
      )

      userStorage.set('likedPlaces', [
        likedPlace,
        ...withoutDuplicate,
      ])

      showToast('Place saved to Liked Places!')
      return
    }

    setPlaces(prev => prev.filter(item => getPlaceId(item) !== placeId))
    showToast("Feedback noted. We'll skip it next time.")
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
                  key={getPlaceId(place)}
                  place={place}
                  feedback={feedback[getPlaceId(place)]}
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
