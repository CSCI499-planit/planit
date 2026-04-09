export default function HomePage() {
  const trips = [
    { city: 'New York City', region: 'New York', dates: 'March 28, 2025 – Apr 10, 2025', img: 'https://images.unsplash.com/photo-1496442226666-8d4d0e62e6e9?w=800&q=80' },
    { city: 'Paris', region: 'France', dates: 'Jun 1, 2025 – Jun 14, 2025', img: 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=800&q=80' },
  ]

  return (
    <div className="page">
      <div className="home__hero">
        <h1>Welcome back, Dask!</h1>
        <p>Ready to start a new adventure?</p>
        <div className="home__actions">
          <button className="btn btn--primary">Create a new trip</button>
          <button className="btn btn--secondary">Explore top destinations</button>
        </div>
      </div>

      <div className="stats-row">
        {[
          ['Active Trips', '1'],
          ['Countries', '20'],
          ['Days Planned', '40'],
          ['Total Spent This Year', '$2,300'],
          ['Trips Completed', '5'],
        ].map(([label, val]) => (
          <div className="stats-card" key={label}>
            <span className="stats-card__val">{val}</span>
            <span className="stats-card__label">{label}</span>
          </div>
        ))}
      </div>

      <h2 className="section-title">Planned Trips</h2>
      <div className="trip-list">
        {trips.map(t => (
          <div className="trip-card" key={t.city}>
            <img src={t.img} alt={t.city} className="trip-card__img" />
            <div className="trip-card__overlay">
              <span className="trip-card__city">📍 {t.city}, {t.region}</span>
              <span className="trip-card__dates">{t.dates}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}