import { useState } from "react"
import { userStorage } from '../utils/userStorage'

const INTERESTS = [
  { id: "outdoor", label: "Outdoor adventures" },
  { id: "cultural", label: "Art & museums" },
  { id: "food_and_drink", label: "Food & drink" },
  { id: "nightlife", label: "Nightlife" },
  { id: "shopping", label: "Shopping" },
  { id: "wellness", label: "Wellness" },
  { id: "historical", label: "History" },
  { id: "scenic", label: "Scenic spots" },
  { id: "adventurous", label: "Adventurous" },
  { id: "family_friendly", label: "Family-friendly" },
  { id: "romantic", label: "Romantic" },
  { id: "pet_friendly", label: "Pet-friendly" },
  { id: "upscale", label: "Upscale" },
  { id: "budget_friendly", label: "Budget-friendly" },
]

const BUDGET_LABELS = { '1':'Free/nearly free','2':'Budget-conscious','3':'Moderate','4':'Comfortable','5':'No limit' }
const PACE_LABELS = ['Packed','Balanced','Relaxed']
const TRAVEL_MODES = ['Walking','Biking','Public Transit','Driving','Other']

function PrefsEditor({ prefs, onSave, onCancel }) {
  const [form, setForm] = useState({ ...prefs })
  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }))
  const toggle = (k, v) => setForm(prev => ({ ...prev, [k]: prev[k]?.includes(v) ? prev[k].filter(x => x !== v) : [...(prev[k]||[]), v] }))

  return (
    <div className="prefs-editor">
      <fieldset>
        <legend>Use Case</legend>
        <div className="pref-radio-group">
          {[['local','Local'], ['daytrip','Day trips'], ['travel','Long trips'], ['mixed','All']].map(([v,l]) => (
            <label key={v} className={form.use_case === v ? 'active' : ''}>
              <input type="radio" name="use_case" value={v} checked={form.use_case === v} onChange={() => set('use_case', v)} />
              {l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Traveling as</legend>
        <div className="pref-radio-group">
          {[['solo','Solo'],['couple','Couple'],['friends','Friends'],['family','Family'],['mixed','Mixed']].map(([v,l]) => (
            <label key={v} className={form.party_type === v ? 'active' : ''}>
              <input type="radio" name="party_type" value={v} checked={form.party_type === v} onChange={() => set('party_type', v)} />
              {l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Daily Budget — {BUDGET_LABELS[form.daily_budget_tier]}</legend>
        <input type="range" min="1" max="5" value={form.daily_budget_tier || 3} onChange={e => set('daily_budget_tier', e.target.value)} className="pref-slider" />
      </fieldset>

      <fieldset>
        <legend>Interests</legend>
        <div className="pref-check-group">
          {INTERESTS.map(i => (
            <label key={i.id} className={form.preferred_tags?.includes(i.id) ? 'active' : ''}>
              <input type="checkbox" checked={form.preferred_tags?.includes(i.id)} onChange={() => toggle('preferred_tags', i.id)} />
              {i.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Travel Mode</legend>
        <div className="pref-radio-group">
          {TRAVEL_MODES.map(m => (
            <label key={m} className={form.travel_mode?.[0] === m.toLowerCase().replace(' ','') ? 'active' : ''}>
              <input type="radio" name="travel_mode" value={m} checked={form.travel_mode?.[0] === m.toLowerCase().replace(' ','')} onChange={() => set('travel_mode', [m.toLowerCase().replace(' ','')] )} />
              {m}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Pace</legend>
        <div className="pref-radio-group">
          {PACE_LABELS.map(p => (
            <label key={p} className={form.itinerary_pace === p.toLowerCase() ? 'active' : ''}>
              <input type="radio" name="itinerary_pace" value={p} checked={form.itinerary_pace === p.toLowerCase()} onChange={() => set('itinerary_pace', p.toLowerCase())} />
              {p}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="prefs-editor__actions">
        <button className="btn btn--secondary" onClick={onCancel}>Cancel</button>
        <button className="btn btn--primary" onClick={() => onSave(form)}>Save Preferences</button>
      </div>
    </div>
  )
}

export default function ProfilePage() {
  const [openTrip, setOpenTrip] = useState(null)
  const [darkMode, setDarkMode] = useState(false)
  const [editingPrefs, setEditingPrefs] = useState(false)
  const [prefs, setPrefs] = useState(() => {
    try { return JSON.parse(localStorage.getItem('userPreferences') || 'null') } catch { return null }
  })

  const savePrefs = (updated) => {
    localStorage.setItem('userPreferences', JSON.stringify(updated))
    setPrefs(updated)
    setEditingPrefs(false)
  }

  const past = [
    { city: "Seoul, South Korea", dates: "Nov 1 - Nov 14, 2024", notes: "Food tour + palace visits", img: "https://source.unsplash.com/400x300/?seoul" },
    { city: "Tokyo, Japan", dates: "Sep 3 – Sep 17, 2024", notes: "Shibuya, temples, Mt. Fuji", img: "https://source.unsplash.com/400x300/?tokyo" },
    { city: "Mexico City, Mexico", dates: "Jul 4 – Jul 10, 2024", notes: "Museums + street food", img: "https://source.unsplash.com/400x300/?mexico-city" },
    { city: "New York City, New York", dates: "Jan 1 – Jan 7, 2024", notes: "Broadway + cafés", img: "https://source.unsplash.com/400x300/?new-york-city" },
  ]

  return (
    <div className={`page ${darkMode ? "dark" : ""}`}>
      <div className="profile__header">
        <div className="profile__avatar">DL</div>
        <div className="profile__info">
          <h2>Dask Lanb</h2>
          <p>Not all who wander are lost.</p>
          <p className="profile__badge">Explorer</p>
        </div>
        <div className="profile__stats">
          {[{v:20,l:'Trips',max:50},{v:30,l:'Countries',max:195},{v:89,l:'Days',max:365},{v:3,l:'Friends',max:10}].map(({v,l,max}) => (
            <div className="profile__stat" key={l}>
              <span>{v}</span><small>{l}</small>
              <div className="stat-bar"><div style={{ width:`${(v/max)*100}%` }} /></div>
            </div>
          ))}
        </div>
      </div>

      <div className="profile__body">
        <div className="profile__col">
          <div className="profile__section-header">
            <h3>Past Trips</h3><span>View all</span>
          </div>
          {past.map((t, i) => (
            <div className={`past-trip ${openTrip === i ? "active" : ""}`} key={t.city} onClick={() => setOpenTrip(openTrip === i ? null : i)}>
              <div className="past-trip__img"><img src={t.img} alt={t.city} /></div>
              <span className="past-trip__city">{t.city}</span>
              <span className="past-trip__dates">{t.dates}</span>
              {openTrip === i && (
                <div className="past-trip__details">
                  <p>{t.notes}</p>
                  <button className="btn btn--secondary">View Itinerary</button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="profile__col">
          <div className="profile__section-header">
            <h3>Upcoming Trips</h3><span>All trips →</span>
          </div>
          <div className="upcoming-trip">
            <div className="upcoming-flag"></div>
            <div><strong>Paris, France</strong><p>Jun 1 – Jun 14, 2025</p></div>
          </div>
          <button className="btn btn--primary" style={{ marginTop: "0.75rem" }}>+ Add Trip</button>

          <div className="profile__section-header" style={{ marginTop: "1.5rem" }}>
            <h3>My Preferences</h3>
            <span onClick={() => setEditingPrefs(!editingPrefs)} style={{ cursor:'pointer', color:'#4da3ff' }}>
              {editingPrefs ? 'Cancel' : 'Edit'}
            </span>
          </div>

          {!editingPrefs && prefs && (
            <div className="prefs-summary">
              {prefs.use_case && <div className="pref-row"><span className="pref-label">Use Case</span><span className="pref-val">{prefs.use_case}</span></div>}
              {prefs.party_type && <div className="pref-row"><span className="pref-label">Group</span><span className="pref-val">{prefs.party_type}</span></div>}
              {prefs.itinerary_pace && <div className="pref-row"><span className="pref-label">Pace</span><span className="pref-val">{prefs.itinerary_pace}</span></div>}
              {prefs.daily_budget_tier && <div className="pref-row"><span className="pref-label">Budget</span><span className="pref-val">{BUDGET_LABELS[prefs.daily_budget_tier]}</span></div>}
              {prefs.preferred_tags?.length > 0 && (
                <div className="pref-row pref-row--tags">
                  <span className="pref-label">Interests</span>
                  <div className="pref-tags">{prefs.preferred_tags.map(t => <span key={t} className="pref-tag">{t}</span>)}</div>
                </div>
              )}
            </div>
          )}

          {!editingPrefs && !prefs && (
            <p className="profile__pref-hint">No preferences saved yet. Complete the survey to personalize your experience.</p>
          )}

          {editingPrefs && (
            <PrefsEditor prefs={prefs || {}} onSave={savePrefs} onCancel={() => setEditingPrefs(false)} />
          )}

          <div className="profile__section-header" style={{ marginTop: "1.5rem" }}>
            <h3>Settings</h3>
          </div>
          <label className="toggle">
            <input type="checkbox" checked={darkMode} onChange={() => setDarkMode(!darkMode)} />
            <span>Dark Mode</span>
          </label>
        </div>
      </div>
    </div>
  )
}