import { useState } from 'react'
import destinations from '../data/destinations'

export default function DestinationPage() {
  const [search, setSearch] = useState('')

  const user = JSON.parse(localStorage.getItem('userPreferences'))

  const score = (d) => {
    if (!user) return d.rating

    let s = 0

    d.tags.forEach(tag => {
      if (user.preferred_tags?.includes(tag)) s += 2
    })

    if (user.daily_budget_tier && d.priceLevel <= user.daily_budget_tier) {
      s += 2
    }

    if (d.audience?.includes(user.party_type)) {
      s += 1
    }

    s += (d.rating * (user.popularity_weight || 3)) / 5

    return s
  }

  const filtered = destinations
    .filter(d => d.name.toLowerCase().includes(search.toLowerCase()))
    .map(d => ({ ...d, score: score(d) }))
    .sort((a, b) => b.score - a.score)

  return (
    <div className="dest-page">
      <div className="dest-header">
        <h1 className="dest-title">Recommended Destinations</h1>
        <p className="dest-subtitle">Personalized picks based on your preferences</p>
        <div className="dest-controls">
          <div className="dest-search">
            <input
              placeholder="Search destinations..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="dest-list">
        {filtered.map(d => (
          <div key={d.id} className="dest-card">
            <div className="dest-card__image-wrap">
              <img className="dest-card__image" src={d.img} alt={d.name} />
            </div>
            <div className="dest-card__body">
              <div className="dest-card__name">{d.name}</div>
              <div className="dest-card__meta">⭐ {d.rating}</div>
              <p>{d.description}</p>
              <div className="dest-card__tags">
                {d.tags.map(tag => (
                  <span key={tag} className="dest-tag">{tag}</span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}