import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import { userStorage } from '../utils/userStorage'
import ConfirmDialog from '../components/confirmdialog'
import '../components/home.css'

function openInGoogleMaps(stops) {
  const coords = stops
    .filter(s => s.place?.latitude && s.place?.longitude)
    .map(s => `${s.place.latitude},${s.place.longitude}`)

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

function openDestinationInGoogleMaps(dest) {
  const query = [
    dest.name,
    dest.address,
    dest.city,
    dest.state,
    dest.country || dest.locationQuery,
  ]
    .filter(Boolean)
    .join(', ') || (
    dest.latitude && dest.longitude
      ? `${dest.latitude},${dest.longitude}`
      : ''
  )

  if (!query) return

  window.open(
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`,
    '_blank'
  )
}

function SavedItineraryCard({ entry, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const [confirm, setConfirm] = useState(false)

  const allStops =
    entry.itinerary?.flatMap(d => d.stops) || []

  return (
    <div className="saved-card">
      <div
        className="saved-card__header"
        onClick={() => setExpanded(!expanded)}
      >
        <div>
          <div className="saved-card__title">
            {entry.location}
          </div>

          <div className="saved-card__meta">
            Saved {entry.savedAt}
          </div>
        </div>

        <span className="saved-card__badge">
          {expanded ? '▲ Hide' : '▼ View'}
        </span>
      </div>

      {!expanded && (
        <>
          <div className="saved-card__preview">
            {allStops.slice(0, 3).map((s, i) => (
              <div key={i} className="saved-card__stop">
                <span className="saved-card__stop-dot" />
                {s.place?.name}
              </div>
            ))}
          </div>

          {allStops.length > 3 && (
            <div className="saved-card__more">
              +{allStops.length - 3} more stops
            </div>
          )}
        </>
      )}

      {expanded && (
        <div className="saved-card__detail">
          {entry.itinerary?.map(day => (
            <div key={day.day} className="saved-detail-day">
              <div className="saved-detail-day__header">
                <div className="saved-detail-day__label">
                  Day {day.day}
                  {day.date ? ` · ${day.date}` : ''}
                </div>

                <button
                  className="gmaps-btn"
                  onClick={() => openInGoogleMaps(day.stops)}
                >
                  Open in Google Maps
                </button>
              </div>

              {day.stops.map((s, i) => (
                <div key={i} className="saved-detail-stop">
                  {s.place?.name}

                  {s.arrival_time && (
                    <span style={{ color: '#4a9bc5', marginLeft: 6 }}>
                      {s.arrival_time}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="saved-card__footer">
        <span className="saved-card__days">
          {entry.tripDays} day
          {entry.tripDays !== 1 ? 's' : ''} · {allStops.length} stops
        </span>

        <div className="saved-card__actions">
          <button
            className="gmaps-btn"
            onClick={() => openInGoogleMaps(allStops)}
            disabled={allStops.length === 0}
          >
            Open Trip in Google Maps
          </button>

          <button
            className="saved-card__delete"
            onClick={() => setConfirm(true)}
          >
            Remove
          </button>
        </div>
      </div>

      {confirm && (
        <ConfirmDialog
          message={`Remove your itinerary for ${entry.location}?`}
          onConfirm={() => {
            setConfirm(false)
            onDelete(entry.id)
          }}
          onCancel={() => setConfirm(false)}
        />
      )}
    </div>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [savedItineraries, setSavedItineraries] = useState(
    () => userStorage.get('savedItineraries') || []
  )

  const [likedDests, setLikedDests] = useState(
    () => userStorage.get('likedDestinations') || []
  )

  const [confirmDest, setConfirmDest] = useState(null)

  const deleteItinerary = id => {
    const updated = savedItineraries.filter(e => e.id !== id)
    setSavedItineraries(updated)
    userStorage.set('savedItineraries', updated)
  }

  const removeDest = destId => {
    const updated = likedDests.filter(d => d.id !== destId)
    setLikedDests(updated)
    userStorage.set('likedDestinations', updated)
    setConfirmDest(null)
  }

  const firstName = user?.name?.split(' ')[0] || 'Traveler'

  const hour = new Date().getHours()

  const greeting =
    hour < 12
      ? 'Good morning'
      : hour < 17
      ? 'Good afternoon'
      : 'Good evening'

  return (
    <div className="page">
      <div className="home__hero">
        <h1>
          {greeting}, {firstName}
        </h1>

        <p>
          Ready for your next adventure? Let's make it unforgettable.
        </p>

        <div className="home__actions">
          <button
            className="btn btn--primary"
            onClick={() => navigate('/app/generate-itinerary')}
          >
            Generate Itinerary
          </button>

          <button
            className="btn btn--secondary"
            onClick={() => navigate('/app/generate-places')}
          >
            Discover Places
          </button>

          <button
            className="btn btn--secondary"
            onClick={() => navigate('/app/destination')}
          >
            Explore Destinations
          </button>
        </div>
      </div>

      <div className="stats-row">
        {[
          ['Countries', '20'],
          ['Days Planned', '40'],
          ['Spent This Year', '$2,300'],
          ['Trips Done', '5'],
        ].map(([label, val]) => (
          <div className="stats-card" key={label}>
            <span className="stats-card__val">{val}</span>
            <span className="stats-card__label">{label}</span>
          </div>
        ))}
      </div>

      <h2 className="section-title">Saved Itineraries</h2>

      {savedItineraries.length === 0 ? (
        <p className="section-empty">
          No saved itineraries yet — generate one and save it!
        </p>
      ) : (
        <div className="saved-list">
          {savedItineraries.map(entry => (
            <SavedItineraryCard
              key={entry.id}
              entry={entry}
              onDelete={deleteItinerary}
            />
          ))}
        </div>
      )}

      <h2 className="section-title">Liked Destinations</h2>

      {likedDests.length === 0 ? (
        <p className="section-empty">
          No liked destinations yet; explore destinations to save them here!
        </p>
      ) : (
        <div className="dest-list-home">
          {likedDests.map(dest => (
            <div key={dest.id} className="dest-chip">
              <div className="dest-chip__left">
                <div>
                  <div className="dest-chip__name">
                    {dest.name}
                  </div>

                  <div className="dest-chip__country">
                    {dest.country}
                  </div>
                </div>
              </div>

              <div className="dest-chip__actions">
                <button
                  className="gmaps-btn"
                  onClick={() => openDestinationInGoogleMaps(dest)}
                >
                  Open in Google Maps
                </button>

                <button
                  className="dest-chip__remove"
                  onClick={() => setConfirmDest(dest)}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {confirmDest && (
        <ConfirmDialog
          message={`Remove ${confirmDest.name} from your liked destinations?`}
          onConfirm={() => removeDest(confirmDest.id)}
          onCancel={() => setConfirmDest(null)}
        />
      )}
    </div>
  )
}
