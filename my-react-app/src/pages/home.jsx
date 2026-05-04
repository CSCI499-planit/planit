import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function HomePage() {
  const navigate = useNavigate()
  const { user } = useAuth()

  const likedTrips = JSON.parse(localStorage.getItem('likedTrips')) || []

  return (
    <div className="page">

      <div className="home__hero">
        <h1>
          Welcome back, {user?.name ? user.name.split(' ')[0] : 'Dask'}!
        </h1>

        <p>Plan, explore, and build your next adventure.</p>

        <div className="home__actions">
          <button
            className="btn btn--primary"
            onClick={() => navigate('/app/generate')}
          >
            Generate itinerary
          </button>

          <button
            className="btn btn--secondary"
            onClick={() => navigate('/app/destination')}
          >
            Explore top destinations
          </button>
        </div>
      </div>

      <div className="stats-row">
        {[
          ['Countries', '20'],
          ['Days Planned', '40'],
          ['Total Spent This Year', '2,300'],
          ['Trips Completed', '5'],
        ].map(([label, val]) => (
          <div className="stats-card" key={label}>
            <span className="stats-card__val">{val}</span>
            <span className="stats-card__label">{label}</span>
          </div>
        ))}
      </div>

      <h2 className="section-title">Liked Itineraries</h2>

      <div className="trip-list">
        {likedTrips.length === 0 ? (
          <p style={{ padding: '1rem' }}>No liked itineraries yet.</p>
        ) : (
          likedTrips.map((t, idx) => (
            <div className="trip-card" key={idx}>
              <img src={t.img} alt={t.city} className="trip-card__img" />

              <div className="trip-card__overlay">
                <span className="trip-card__city">📍 {t.city}</span>
                <span className="trip-card__dates">{t.dates}</span>
              </div>
            </div>
          ))
        )}
      </div>

    </div>
  )
}