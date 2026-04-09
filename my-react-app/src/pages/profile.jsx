export default function ProfilePage() {
  const past = [
    { city: 'Seoul, South Korea', dates: 'Nov 1 - Nov 14, 2024', color: '#e8f5e9' },
    { city: 'Tokyo, Japan', dates: 'Sep 3 – Sep 17, 2024', color: '#e3f2fd' },
    { city: 'Mexico City, Mexico', dates: 'Jul 4 – Jul 10, 2024', color: '#fce4ec' },
    { city: 'New York City, New York', dates: 'Jan 1 – Jan 7, 2024', color: '#f3e5f5' },
  ]

  return (
    <div className="page">
      <div className="profile__header">
        <div className="profile__avatar">DL</div>
        <div className="profile__info">
          <h2>Dask Lanb</h2>
          <p>Not all who wander are lost.</p>
        </div>
        <div className="profile__stats">
          {[['20', 'Trips'], ['30', 'Countries'], ['89', 'Days'], ['3', 'Friends']].map(([v, l]) => (
            <div className="profile__stat" key={l}>
              <span>{v}</span>
              <small>{l}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="profile__body">
        <div className="profile__col">
          <div className="profile__section-header">
            <h3>Past Trips</h3><span>79 countries</span>
          </div>
          {past.map(t => (
            <div className="past-trip" key={t.city} style={{ background: t.color }}>
              <span className="past-trip__city">{t.city}</span>
              <span className="past-trip__dates">{t.dates}</span>
            </div>
          ))}
        </div>

        <div className="profile__col">
          <div className="profile__section-header">
            <h3>Upcoming Trips</h3><span>All trips →</span>
          </div>
          <div className="upcoming-trip">
            <div className="upcoming-flag">🇫🇷</div>
            <div>
              <strong>Paris, France</strong>
              <p>Jun 1 – Jun 14, 2025</p>
            </div>
          </div>

          <div className="profile__section-header" style={{ marginTop: '1.5rem' }}>
            <h3>Personalization</h3><span>Language</span>
          </div>
          <p className="profile__pref-hint">Edit your preferences here</p>
        </div>
      </div>
    </div>
  )
}