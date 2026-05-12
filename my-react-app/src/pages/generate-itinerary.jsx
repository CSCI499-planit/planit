import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { userStorage } from '../utils/userStorage'
import '../components/generate.css'
import 'azure-maps-control/dist/atlas.min.css'
import * as atlas from 'azure-maps-control'

const DAY_COLORS = [
  '#4a9bc5',
  '#e85d5d',
  '#16a34a',
  '#f59e0b',
  '#8b5cf6',
  '#ec4899',
  '#0ea5e9',
]

function ItineraryMap({ itinerary }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)

  useEffect(() => {
    if (!mapRef.current || !itinerary?.length) return

    const allStops = itinerary
      .flatMap(d => d.stops)
      .filter(s => s.place?.longitude && s.place?.latitude)

    if (!allStops.length) return

    if (mapInstanceRef.current) {
      mapInstanceRef.current.dispose()
      mapInstanceRef.current = null
    }

    const center = [
      allStops[0].place.longitude,
      allStops[0].place.latitude,
    ]

    const map = new atlas.Map(mapRef.current, {
      center,
      zoom: 13,
      authOptions: {
        authType: 'subscriptionKey',
        subscriptionKey: import.meta.env.VITE_AZURE_MAPS_KEY,
      },
      style: 'road',
    })

    mapInstanceRef.current = map

    map.events.add('ready', () => {
      const dataSource = new atlas.source.DataSource()

      map.sources.add(dataSource)

      itinerary.forEach((day, di) => {
        const color = DAY_COLORS[di % DAY_COLORS.length]

        const coords = day.stops
          .filter(s => s.place?.longitude && s.place?.latitude)
          .map(s => [s.place.longitude, s.place.latitude])

        if (coords.length > 1) {
          dataSource.add(
            new atlas.data.Feature(
              new atlas.data.LineString(coords),
              { color }
            )
          )
        }

        coords.forEach((coord, si) => {
          const stop = day.stops[si]

          dataSource.add(
            new atlas.data.Feature(
              new atlas.data.Point(coord),
              {
                label: String(si + 1),
                name: stop.place.name,
                color,
                day: day.day,
              }
            )
          )
        })
      })

      map.layers.add(
        new atlas.layer.LineLayer(dataSource, null, {
          strokeColor: ['get', 'color'],
          strokeWidth: 3,
          strokeDashArray: [2, 2],
          filter: ['==', ['geometry-type'], 'LineString'],
        })
      )

      map.layers.add(
        new atlas.layer.BubbleLayer(dataSource, null, {
          color: ['get', 'color'],
          radius: 14,
          strokeColor: '#fff',
          strokeWidth: 2,
          filter: ['==', ['geometry-type'], 'Point'],
        })
      )

      map.layers.add(
        new atlas.layer.SymbolLayer(dataSource, null, {
          textOptions: {
            textField: ['get', 'label'],
            color: '#fff',
            size: 12,
            font: ['StandardFont-Bold'],
            offset: [0, 0.1],
          },
          iconOptions: {
            image: 'none',
          },
          filter: ['==', ['geometry-type'], 'Point'],
        })
      )
    })

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.dispose()
        mapInstanceRef.current = null
      }
    }
  }, [itinerary])

  return <div ref={mapRef} className="itinerary-map" />
}

function formatTime(t) {
  if (!t) return null

  const [h, m] = t.split(':').map(Number)

  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${
    h >= 12 ? 'PM' : 'AM'
  }`
}

function Stars({ rating, reviewCount }) {
  if (!rating && !reviewCount) {
    return <span className="stop-no-rating">No rating yet</span>
  }

  const stars = rating ? Math.round(rating) : 0

  return (
    <span className="stop-stars">
      {[1, 2, 3, 4, 5].map(i => (
        <span
          key={i}
          className={i <= stars ? 'star filled' : 'star'}
        >
          {i <= stars ? '★' : '☆'}
        </span>
      ))}

      {rating && (
        <span className="stop-rating-val">
          {rating.toFixed(1)}
        </span>
      )}

      {reviewCount && (
        <span className="stop-review-count">
          ({reviewCount.toLocaleString()})
        </span>
      )}
    </span>
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

function StopCard({ stop }) {
  const {
    place,
    arrival_time,
    departure_time,
    travel_to_next,
  } = stop

  const timeStr =
    arrival_time && departure_time
      ? `${formatTime(arrival_time)} – ${formatTime(
          departure_time
        )}`
      : arrival_time
      ? formatTime(arrival_time)
      : null

  const displayAddr =
    [place.street, place.suburb || place.district, place.city, place.state]
      .filter(Boolean)
      .slice(0, 3)
      .join(', ') ||
    place.address?.split(',').slice(0, 3).join(',')

  return (
    <div className="stop-item">
      <div className="stop-dot" />

      <div className="stop-card">
        <div className="stop-card__top">
          <span className="stop-card__name">
            {place.name}
          </span>

          {timeStr && (
            <span className="stop-card__time">
              {timeStr}
            </span>
          )}
        </div>

        <div className="stop-card__meta-row">
          <Stars
            rating={place.rating}
            reviewCount={place.review_count}
          />

          <PriceLevel level={place.price_level} />
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

        {travel_to_next && (
          <div className="stop-card__travel">
            {travel_to_next.duration_minutes} min
            {travel_to_next.distance_m > 0 && (
              <> · {travel_to_next.distance_m >= 1609
                ? `${(travel_to_next.distance_m / 1609.34).toFixed(1)} mi`
                : `${Math.round(travel_to_next.distance_m * 3.281)} ft`} to next stop</>
            )}
            {!travel_to_next.distance_m && <> to next stop</>}
          </div>
        )}
      </div>
    </div>
  )
}

function openInGoogleMaps(stops) {
  const coords = stops
    .filter(
      s => s.place?.latitude && s.place?.longitude
    )
    .map(
      s => `${s.place.latitude},${s.place.longitude}`
    )

  if (coords.length === 0) return

  const origin = coords[0]
  const destination = coords[coords.length - 1]

  const waypoints = coords
    .slice(1, -1)
    .slice(0, 8)
    .join('|')

  const url = `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${destination}${
    waypoints ? `&waypoints=${waypoints}` : ''
  }&travelmode=driving`

  window.open(url, '_blank')
}

function DayCard({
  dayData,
  onLike,
  onDislike,
  feedback,
}) {
  const ordinals = [
    '',
    'First',
    'Second',
    'Third',
    'Fourth',
    'Fifth',
    'Sixth',
    'Seventh',
  ]

  return (
    <div className="day-card">
      <div className="day-card__label">
        <div className="day-card__num">
          {dayData.day}
        </div>

        <span className="day-card__title">
          {ordinals[dayData.day] ||
            `Day ${dayData.day}`}{' '}
          Day
        </span>

        {dayData.date && (
          <span className="day-card__date">
            {dayData.date}
          </span>
        )}

        <div className="day-card__actions">
          <button
            className="gmaps-btn"
            onClick={() =>
              openInGoogleMaps(dayData.stops)
            }
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

      <div className="stops-timeline">
        {dayData.stops.map((stop, i) => (
          <StopCard key={i} stop={stop} />
        ))}
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
  const [feedback, setFeedback] = useState({})
  const resultsRef = useRef(null)

// mouse glow effect
useEffect(() => {
  const handleMouseMove = (e) => {
    const x = (e.clientX / window.innerWidth) * 100
    const y = (e.clientY / window.innerHeight) * 100

    const el = document.querySelector('.generate-page')

    if (!el) return

    el.style.setProperty('--x', `${x}%`)
    el.style.setProperty('--y', `${y}%`)
  }

  window.addEventListener('mousemove', handleMouseMove)

  return () => {
    window.removeEventListener(
      'mousemove',
      handleMouseMove
    )
  }
}, [])

// scroll color shift
useEffect(() => {
  const handleScroll = () => {
    const scrollY = window.scrollY

    const max =
      document.body.scrollHeight -
      window.innerHeight

    const progress =
      max > 0 ? scrollY / max : 0

    const hue = 200 + progress * 100

    const el = document.querySelector(
      '.generate-page'
    )

    if (!el) return

    el.style.setProperty('--hue', hue)
  }

  window.addEventListener('scroll', handleScroll)

  return () => {
    window.removeEventListener(
      'scroll',
      handleScroll
    )
  }
}, [])

  const showToast = msg => {
    setToast(msg)

    setTimeout(() => {
      setToast('')
    }, 2800)
  }

  const handleFeedback = async (day, type) => {
    if (feedback[day]) return

    setFeedback(prev => ({
      ...prev,
      [day]: type,
    }))

    const eventType =
      type === 'like'
        ? 'itinerary_like'
        : 'itinerary_dislike'

    const placeId = `itinerary_${location
      .toLowerCase()
      .replace(/\s+/g, '_')}_day${day}`

    try {
      await api.post('/interactions/', {
        place_id: placeId,
        event_type: eventType,
      })
    } catch {
      // non-fatal
    }

    if (type === 'like' && itinerary) {
      const existing =
        userStorage.get('savedItineraries') || []

      const alreadySaved = existing.some(
        item =>
          item.location === location &&
          item.tripDays === tripDays
      )

      if (!alreadySaved) {
        userStorage.set('savedItineraries', [
          {
            id: Date.now(),
            location,
            tripDays,
            savedAt:
              new Date().toLocaleDateString(),
            itinerary,
          },
          ...existing,
        ])
      }

      setSaved(true)

      showToast(
        'Itinerary liked and saved to your home page!'
      )
    } else {
      showToast(
        "Got it; we'll improve future recommendations."
      )
    }
  }

  const handleSubmit = async e => {
    e.preventDefault()

    setError('')
    setLoading(true)
    setSaved(false)
    setItinerary(null)
    setFeedback({})

    try {
      const data = await api.post(
        '/recommend/itinerary',
        {
          location,
          trip_days: tripDays,
          top_k: 20,
          radius_m: 3000,
          limit: 50,
        }
      )

      setItinerary(data.itinerary)
    } catch (err) {
      setError(
        err.message ||
          'Failed to generate itinerary'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="generate-page">
      <div className="generate-container">
        <h1>
          Plan your trip, <em>instantly.</em>
        </h1>

        <p className="generate-subtitle">
          Enter a destination and we'll create a
          personalized day-by-day trip plan with
          restaurants, attractions, and optimized
          routes.
        </p>

    <div className="generate-instructions">
      <p>How it works:</p>

      <ul>
        <li>
          First, choose any city, neighborhood, or destination.

          <ul>
            <li>
              Please write as "[Neighborhood], [City]" for best results. e.g. "Brooklyn, New York"
            </li>
          </ul>
        </li>

        <li>
          Next, select how many days you're traveling (we recommend 1-3 for now).
        </li>

        <li>
          Then, press "Generate Itinerary." We'll automatically organize nearby places into daily plans.
        </li>

        <li>
          Feel free to use “Open in Google Maps” to explore the area and get directions.
        </li>

        <li>
          If you like the recommendation, click "Like" to save it to your home page.
        </li>

        <li>
          If not, click "Dislike" and we'll use that feedback to improve future suggestions.
        </li>
      </ul>
    </div>

        <form
          onSubmit={handleSubmit}
          className="generate-form"
        >
          <div className="form-group">
            <label htmlFor="location">
              Destination
            </label>

            <input
              id="location"
              type="text"
              placeholder="e.g., Brooklyn, New York"
              value={location}
              onChange={e =>
                setLocation(e.target.value)
              }
              required
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="trip_days">
                Duration (days)
              </label>

              <input
                id="trip_days"
                type="number"
                min="1"
                max="7"
                value={tripDays}
                onChange={e =>
                  setTripDays(
                    parseInt(e.target.value)
                  )
                }
              />
            </div>
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn--primary"
            disabled={loading}
          >
            {loading
              ? 'Building your itinerary…'
              : 'Generate Itinerary'}
          </button>
        </form>

        {itinerary && (
          <div className="itinerary-result" ref={resultsRef}>
            <div className="itinerary-header">
              <h2>
                Your trip to <span>{location}</span>
              </h2>
            </div>

            {itinerary.length === 0 ? (
              <div className="empty-itinerary">
                No stops found. Try a different
                destination!
              </div>
            ) : (
              <>
                <ItineraryMap itinerary={itinerary} />

                {itinerary.map(day => (
                  <DayCard
                    key={day.day}
                    dayData={day}
                    feedback={feedback[day.day]}
                    onLike={() => handleFeedback(day.day, 'like')}
                    onDislike={() => handleFeedback(day.day, 'dislike')}
                  />
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {toast && (
        <div className="toast">{toast}</div>
      )}
    </div>

    
  )
}
