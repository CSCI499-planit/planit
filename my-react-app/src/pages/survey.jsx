import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function SurveyPage() {
  const navigate = useNavigate()

  const [answers, setAnswers] = useState({
    use_case: '',
    party_type: '',
    daily_budget_tier: '',
    trip_budget_tier: '',
    preferred_tags: [],
    exploration_score: 3,
    popularity_weight: 3,
    cuisine_preferences: [],
    dietary_restrictions: [],
    travel_mode: '',
    max_travel_minutes: '',
    itinerary_pace: '',
    maps_history: '',
  })

  const set = (key, val) => setAnswers(prev => ({ ...prev, [key]: val }))

  const toggleList = (key, val) => {
    setAnswers(prev => ({
      ...prev,
      [key]: prev[key].includes(val)
        ? prev[key].filter(v => v !== val)
        : [...prev[key], val],
    }))
  }

  const TAG_MAP = {
    food_and_drink: 'food',
    cultural: 'culture',
    outdoor: 'nature',
    historical: 'history',
    adventurous: 'adventure',
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    const normalized = {
      ...answers,
      preferred_tags: answers.preferred_tags.map(t => TAG_MAP[t] || t),
      daily_budget_tier: Number(answers.daily_budget_tier),
      trip_budget_tier:
        answers.trip_budget_tier === 'null'
          ? null
          : Number(answers.trip_budget_tier),
      max_travel_minutes: Number(answers.max_travel_minutes),
    }

    localStorage.setItem('userPreferences', JSON.stringify(normalized))
    navigate('/app/destination')
  }

  const interests = [
    { id: 'outdoor', label: 'Outdoor adventures' },
    { id: 'cultural', label: 'Art & culture' },
    { id: 'food_and_drink', label: 'Food & restaurants' },
    { id: 'nightlife', label: 'Nightlife' },
    { id: 'shopping', label: 'Shopping' },
    { id: 'wellness', label: 'Wellness' },
    { id: 'historical', label: 'History' },
    { id: 'scenic', label: 'Scenic spots' },
    { id: 'adventurous', label: 'Adventure sports' },
    { id: 'family_friendly', label: 'Family-friendly' },
    { id: 'romantic', label: 'Romantic' },
  ]

  return (
    <div className="survey-page">
      <div className="survey-container">
        <h1>Personalize Your Experience</h1>

        <form onSubmit={handleSubmit} className="survey-form">

          <fieldset>
  <legend>Who are you planning for?</legend>
  <div className="radio-group">
    {['solo', 'couple', 'friends', 'family'].map(val => (
      <label key={val}>
        <input
          type="radio"
          name="party_type"
          checked={answers.party_type === val}
          onChange={() => set('party_type', val)}
        />
        {val.charAt(0).toUpperCase() + val.slice(1)}
      </label>
    ))}
  </div>
</fieldset>

<fieldset>
  <legend>Budget</legend>
  <div className="radio-group">
    {[1, 2, 3, 4].map(val => (
      <label key={val}>
        <input
          type="radio"
          name="daily_budget_tier"
          checked={answers.daily_budget_tier == val}
          onChange={() => set('daily_budget_tier', val)}
        />
        {['Budget', 'Moderate', 'Comfortable', 'Luxury'][val - 1]}
      </label>
    ))}
  </div>
</fieldset>

<fieldset>
  <legend>Interests</legend>
  <div className="checkbox-grid">
    {interests.map(i => (
      <label key={i.id}>
        <input
          type="checkbox"
          checked={answers.preferred_tags.includes(i.id)}
          onChange={() => toggleList('preferred_tags', i.id)}
        />
        {i.label}
      </label>
    ))}
  </div>
</fieldset>

<button type="submit" className="survey-btn">Get Recommendations →</button>

        </form>
      </div>
    </div>
  )
}