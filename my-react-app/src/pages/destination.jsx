import { useState } from 'react'
import destinations from '../data/destinations'
import "../components/destination.css";

const StarIcon = () => (
  <svg viewBox="0 0 12 12" width="11" height="11" fill="currentColor">
    <path d="M6 0l1.5 4.5H12L8.25 7.5 9.75 12 6 9l-3.75 3 1.5-4.5L0 4.5h4.5z" />
  </svg>
)

const HeartFilled = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="#e11d48" stroke="#e11d48" strokeWidth="1.5">
    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
  </svg>
)

const HeartOutline = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#94a3b8" strokeWidth="1.5">
    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
  </svg>
)

const XIcon = ({ active }) => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke={active ? '#475569' : '#94a3b8'} strokeWidth={active ? 2.2 : 2} strokeLinecap="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
)

const PriceDots = ({ level }) => (
  <span className="price-dots">
    {[1, 2, 3].map(i => (
      <span key={i} className={`price-dot ${i <= level ? 'filled' : ''}`} />
    ))}
  </span>
)

export default function DestinationPage() {
  const [search, setSearch] = useState('')
  const [liked, setLiked] = useState({})
  const [disliked, setDisliked] = useState({})

  const user = (() => {
    try { return JSON.parse(localStorage.getItem('userPreferences')) }
    catch { return null }
  })()

  const score = (d) => {
    if (!user) return d.rating
    let s = 0
    d.tags.forEach(tag => {
      if (user.preferred_tags?.includes(tag)) s += 2
    })
    if (user.daily_budget_tier && d.priceLevel <= user.daily_budget_tier) s += 2
    if (d.audience?.includes(user.party_type)) s += 1
    s += (d.rating * (user.popularity_weight || 3)) / 5
    return s
  }

  const handleLike = (id) => {
    setLiked(prev => ({ ...prev, [id]: !prev[id] }))
    setDisliked(prev => ({ ...prev, [id]: false }))
  }

  const handleDislike = (id) => {
    setDisliked(prev => ({ ...prev, [id]: !prev[id] }))
    setLiked(prev => ({ ...prev, [id]: false }))
  }

  const filtered = destinations
    .filter(d =>
      d.name.toLowerCase().includes(search.toLowerCase()) ||
      d.country.toLowerCase().includes(search.toLowerCase()) ||
      d.tags.some(t => t.includes(search.toLowerCase()))
    )
    .map(d => ({ ...d, score: score(d) }))
    .sort((a, b) => b.score - a.score)

  return (
    <div className="dest-page">
      <div className="dest-header">
        <h1 className="dest-title">Recommended Destinations</h1>
        <p className="dest-subtitle">Personalized picks based on your preferences</p>
        <div className="dest-search">
          <input
            placeholder="Search destinations..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="dest-list">
        {filtered.length === 0 ? (
          <div className="dest-empty">No destinations match your search.</div>
        ) : (
          filtered.map(d => (
            <div key={d.id} className="dest-card">
              <div className="dest-card__image-wrap">
                <img
                  className="dest-card__image"
                  src={d.img}
                  alt={d.name}
                  loading="lazy"
                  onError={e => {
                    e.target.style.display = 'none'
                    e.target.nextSibling.style.display = 'flex'
                  }}
                />
                <div className="dest-card__img-fallback">{d.name}</div>
              </div>

              <div className="dest-card__body">
                <div className="dest-card__header">
                  <div className="dest-card__name">{d.name}</div>
                  <div className="dest-card__rating">
                    <StarIcon /> {d.rating}
                  </div>
                </div>

                <div className="dest-card__meta">
                  {d.country}&nbsp;·&nbsp;<PriceDots level={d.priceLevel} />
                </div>

                <p className="dest-card__desc">{d.description}</p>

                <div className="dest-card__tags">
                  {d.tags.map(tag => (
                    <span key={tag} className="dest-tag">{tag}</span>
                  ))}
                </div>

                <div className="dest-actions">
                  <button
                    className={`icon-btn dislike ${disliked[d.id] ? 'active' : ''}`}
                    onClick={() => handleDislike(d.id)}
                    aria-label="Not for me"
                  >
                    <XIcon active={disliked[d.id]} />
                  </button>
                  <button
                    className={`icon-btn like ${liked[d.id] ? 'active' : ''}`}
                    onClick={() => handleLike(d.id)}
                    aria-label="Save"
                  >
                    {liked[d.id] ? <HeartFilled /> : <HeartOutline />}
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}