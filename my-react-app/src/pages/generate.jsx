import { useState } from 'react'
import { api } from '../api/client'
import '../components/generate.css'

export default function GeneratePage() {
  const [location, setLocation] = useState('')
  const [tripDays, setTripDays] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [itinerary, setItinerary] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const body = {
        location,
        trip_days: tripDays,
        top_k: 20,
        radius_m: 5000,
        limit: 50,
      }

      const data = await api.post('/recommend/itinerary', body)
      setItinerary(data.itinerary)
    } catch (err) {
      setError(err.message || 'Failed to generate itinerary')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="generate-page">
      <div className="generate-container">
        <h1>Generate Your Itinerary</h1>

        <form onSubmit={handleSubmit} className="generate-form">
          <div className="form-group">
            <label htmlFor="location">Location *</label>
            <input
              id="location"
              type="text"
              placeholder="e.g., Brooklyn, New York"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="trip_days">Trip Duration (days)</label>
            <input
              id="trip_days"
              type="number"
              min="1"
              max="7"
              value={tripDays}
              onChange={(e) => setTripDays(parseInt(e.target.value))}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="btn btn--primary" disabled={loading}>
            {loading ? 'Generating...' : 'Generate Itinerary'}
          </button>
        </form>
      </div>
    </div>
  )
}