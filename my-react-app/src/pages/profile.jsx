import { useState } from "react";

export default function ProfilePage() {
  const [openTrip, setOpenTrip] = useState(null);
  const [darkMode, setDarkMode] = useState(false);

  const past = [
    {
      city: "Seoul, South Korea",
      dates: "Nov 1 - Nov 14, 2024",
      notes: "Food tour + palace visits",
      img: "https://source.unsplash.com/400x300/?seoul",
    },
    {
      city: "Tokyo, Japan",
      dates: "Sep 3 – Sep 17, 2024",
      notes: "Shibuya, temples, Mt. Fuji",
      img: "https://source.unsplash.com/400x300/?tokyo",
    },
    {
      city: "Mexico City, Mexico",
      dates: "Jul 4 – Jul 10, 2024",
      notes: "Museums + street food",
      img: "https://source.unsplash.com/400x300/?mexico-city",
    },
    {
      city: "New York City, New York",
      dates: "Jan 1 – Jan 7, 2024",
      notes: "Broadway + cafés",
      img: "https://source.unsplash.com/400x300/?new-york-city",
    },
  ];

  return (
    <div className={`page ${darkMode ? "dark" : ""}`}>
      {/* ───── HEADER ───── */}
      <div className="profile__header">
        <div className="profile__avatar">DL</div>

        <div className="profile__info">
          <h2>Dask Lanb</h2>
          <p>Not all who wander are lost.</p>
          <p className="profile__badge">🌍 Explorer</p>
        </div>

        <div className="profile__stats">
          {[
            { v: 20, l: "Trips", max: 50 },
            { v: 30, l: "Countries", max: 195 },
            { v: 89, l: "Days", max: 365 },
            { v: 3, l: "Friends", max: 10 },
          ].map(({ v, l, max }) => (
            <div className="profile__stat" key={l}>
              <span>{v}</span>
              <small>{l}</small>
              <div className="stat-bar">
                <div style={{ width: `${(v / max) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ───── BODY ───── */}
      <div className="profile__body">
        {/* ───── LEFT: PAST TRIPS ───── */}
        <div className="profile__col">
          <div className="profile__section-header">
            <h3>Past Trips</h3>
            <span>View all</span>
          </div>

          {past.map((t, i) => (
            <div
              className={`past-trip ${openTrip === i ? "active" : ""}`}
              key={t.city}
              onClick={() =>
                setOpenTrip(openTrip === i ? null : i)
              }
            >
              <div className="past-trip__img">
                <img src={t.img} alt={t.city} />
              </div>

              <span className="past-trip__city">{t.city}</span>
              <span className="past-trip__dates">{t.dates}</span>

              {openTrip === i && (
                <div className="past-trip__details">
                  <p>{t.notes}</p>
                  <button className="btn btn--secondary">
                    View Itinerary
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* ───── RIGHT: UPCOMING + SETTINGS ───── */}
        <div className="profile__col">
          <div className="profile__section-header">
            <h3>Upcoming Trips</h3>
            <span>All trips →</span>
          </div>

          <div className="upcoming-trip">
            <div className="upcoming-flag">🇫🇷</div>
            <div>
              <strong>Paris, France</strong>
              <p>Jun 1 – Jun 14, 2025</p>
            </div>
          </div>

          <button
            className="btn btn--primary"
            style={{ marginTop: "0.75rem" }}
          >
            + Add Trip
          </button>

          {/* ───── PERSONALIZATION ───── */}
          <div
            className="profile__section-header"
            style={{ marginTop: "1.5rem" }}
          >
            <h3>Personalization</h3>
            <span>Preferences</span>
          </div>

          <label className="toggle">
            <input
              type="checkbox"
              checked={darkMode}
              onChange={() => setDarkMode(!darkMode)}
            />
            <span>Dark Mode</span>
          </label>

          <p className="profile__pref-hint">
            Customize your experience
          </p>
        </div>
      </div>
    </div>
  );
}