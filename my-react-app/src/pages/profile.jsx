import { useState, useRef, useCallback, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from '../context/useAuth'
import * as topojson from "topojson-client"
import { geoMercator, geoPath } from "d3-geo"

import {
  Trees, Utensils, Music2, ShoppingBag, Dumbbell,
  Landmark, Camera, Mountain, Users, Heart,
  PawPrint, Gem, Wallet, MapPin, Link, Copy,
  Check, LogOut, Save,
} from "lucide-react"

// ─── NUMERIC ISO → ISO-2 MAP ─────────────────────────────────────────────────
// world-atlas countries-110m uses numeric IDs on each feature.
// Antarctica (010) is intentionally omitted so it's never toggled.
const NUMERIC_TO_ISO2 = {
  "036":"AU","040":"AT","050":"BD","056":"BE","064":"BT","068":"BO",
  "070":"BA","076":"BR","096":"BN","100":"BG","104":"MM","108":"BI",
  "112":"BY","116":"KH","120":"CM","124":"CA","140":"CF","144":"LK",
  "148":"TD","156":"CN","170":"CO","178":"CG","180":"CD","188":"CR",
  "191":"HR","192":"CU","203":"CZ","208":"DK","214":"DO","218":"EC",
  "222":"SV","231":"ET","233":"EE","246":"FI","250":"FR","266":"GA",
  "268":"GE","276":"DE","288":"GH","300":"GR","320":"GT","324":"GN",
  "328":"GY","332":"HT","340":"HN","348":"HU","356":"IN","360":"ID",
  "364":"IR","380":"IT","384":"CI","388":"JM","392":"JP","398":"KZ",
  "404":"KE","410":"KR","417":"KG","418":"LA","428":"LV","434":"LY",
  "440":"LT","458":"MY","462":"MV","466":"ML","478":"MR","484":"MX",
  "496":"MN","499":"ME","504":"MA","508":"MZ","524":"NP","528":"NL",
  "554":"NZ","558":"NI","562":"NE","566":"NG","578":"NO","586":"PK",
  "591":"PA","600":"PY","604":"PE","608":"PH","616":"PL","620":"PT",
  "626":"TL","630":"PR","642":"RO","643":"RU","646":"RW","682":"SA",
  "686":"SN","688":"RS","694":"SL","703":"SK","704":"VN","705":"SI",
  "706":"SO","710":"ZA","724":"ES","729":"SD","740":"SR","752":"SE",
  "756":"CH","762":"TJ","764":"TH","780":"TT","788":"TN","792":"TR",
  "795":"TM","800":"UG","804":"UA","807":"MK","818":"EG","826":"GB",
  "834":"TZ","840":"US","854":"BF","858":"UY","860":"UZ","862":"VE",
  "887":"YE","894":"ZM","716":"ZW","012":"DZ","008":"AL","031":"AZ",
  "051":"AM","032":"AR","275":"PS","422":"LB","400":"JO","760":"SY",
  "368":"IQ","414":"KW","048":"BH","634":"QA","784":"AE","512":"OM",
}

const WORLD_COUNTRY_COUNT = 195
const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"

// ─── WORLD MAP (pure SVG via d3-geo, no react-simple-maps) ───────────────────

function WorldMap({ visited, onToggle, onFeaturesLoaded }) {
  const [features, setFeatures]   = useState([])
  const [paths,    setPaths]       = useState([])   // precomputed path strings
  const [tooltip,  setTooltip]     = useState(null)
  const [pan,      setPan]         = useState({ x: 0, y: 0 })
  const [zoom,     setZoom]        = useState(1)
  const dragging = useRef(false)
  const lastPos  = useRef({ x: 0, y: 0 })
  const onFeaturesLoadedRef = useRef(onFeaturesLoaded)
  const W = 800, H = 420

  useEffect(() => { onFeaturesLoadedRef.current = onFeaturesLoaded }, [onFeaturesLoaded])

  // Fetch + convert TopoJSON once
  useEffect(() => {
    fetch(GEO_URL)
      .then(r => r.json())
      .then(world => {
        const feats = topojson.feature(world, world.objects.countries).features
        // Filter Antarctica
        const filtered = feats.filter(f => String(f.id) !== "010")
        setFeatures(filtered)
        const meta = filtered
          .map(f => ({ iso2: NUMERIC_TO_ISO2[String(f.id)], name: f.properties?.name ?? "" }))
          .filter(m => m.iso2 && m.name)
          .sort((a, b) => a.name.localeCompare(b.name))
        if (typeof onFeaturesLoadedRef.current === "function") onFeaturesLoadedRef.current(meta)

        const projection = geoMercator()
          .scale(130)
          .translate([W / 2, H / 2 + 40])
          .center([0, 10])

        const pathGen = geoPath().projection(projection)
        setPaths(filtered.map(f => ({ id: f.id, d: pathGen(f) ?? "", name: f.properties?.name ?? "" })))
      })
      .catch(console.error)
  }, [])

  const handleZoomIn  = () => setZoom(z => Math.min(z * 1.4, 6))
  const handleZoomOut = () => setZoom(z => Math.max(z / 1.4, 1))

  // Drag-to-pan
  const onMouseDown = (e) => {
    dragging.current = true
    lastPos.current  = { x: e.clientX, y: e.clientY }
  }
  const onMouseMove = (e) => {
    if (!dragging.current) return
    const dx = e.clientX - lastPos.current.x
    const dy = e.clientY - lastPos.current.y
    lastPos.current = { x: e.clientX, y: e.clientY }
    setPan(p => ({ x: p.x + dx, y: p.y + dy }))
  }
  const onMouseUp = () => { dragging.current = false }

  // Touch pan
  const lastTouch = useRef(null)
  const onTouchStart = (e) => { lastTouch.current = e.touches[0] }
  const onTouchMove  = (e) => {
    if (!lastTouch.current) return
    const t  = e.touches[0]
    const dx = t.clientX - lastTouch.current.clientX
    const dy = t.clientY - lastTouch.current.clientY
    lastTouch.current = t
    setPan(p => ({ x: p.x + dx, y: p.y + dy }))
  }

  return (
    <div
      className="world-map-wrap"
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={() => { dragging.current = false; setTooltip(null) }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={() => { lastTouch.current = null }}
      style={{ cursor: dragging.current ? "grabbing" : "grab" }}
    >
      {/* Zoom controls */}
      <div className="map-controls">
        <button onClick={handleZoomIn}  aria-label="Zoom in">+</button>
        <button onClick={handleZoomOut} aria-label="Zoom out">−</button>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div className="map-tooltip" style={{ left: tooltip.x, top: tooltip.y }}>
          {tooltip.name}{tooltip.visited ? " ✓" : ""}
        </div>
      )}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        {/* Ocean */}
        <rect width={W} height={H} fill="rgba(0,8,22,0.9)" />

        {/* Subtle grid */}
        {[80,160,240,320].map(y => (
          <line key={y} x1={0} y1={y} x2={W} y2={y}
            stroke="rgba(255,255,255,0.025)" strokeWidth="1" />
        ))}
        {[100,200,300,400,500,600,700].map(x => (
          <line key={x} x1={x} y1={0} x2={x} y2={H}
            stroke="rgba(255,255,255,0.025)" strokeWidth="1" />
        ))}

        {/* Countries */}
        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom}) translate(${-W*(zoom-1)/(2*zoom)},${-H*(zoom-1)/(2*zoom)})`}>
          {paths.map(({ id, d, name }) => {
            const iso2      = NUMERIC_TO_ISO2[String(id)]
            const isVisited = iso2 ? visited.includes(iso2) : false

            return (
              <path
                key={id}
                d={d}
                fill={isVisited ? "rgba(0,217,255,0.32)" : "rgba(255,255,255,0.05)"}
                stroke={isVisited ? "rgba(103,211,255,0.55)" : "rgba(255,255,255,0.09)"}
                strokeWidth={0.5 / zoom}
                style={{
                  cursor:     iso2 ? "pointer" : "default",
                  transition: "fill 0.15s ease",
                }}
                onClick={(e) => {
                  e.stopPropagation()
                  if (iso2) onToggle(iso2)
                }}
                onMouseEnter={(e) => {
                  if (!name && !iso2) return
                  const rect = e.currentTarget.closest(".world-map-wrap")?.getBoundingClientRect()
                  setTooltip({
                    name:    name || iso2,
                    visited: isVisited,
                    x: e.clientX - (rect?.left ?? 0) + 12,
                    y: e.clientY - (rect?.top  ?? 0) - 36,
                  })
                }}
                onMouseLeave={() => setTooltip(null)}
              />
            )
          })}
        </g>
      </svg>

      <div className="map-legend">
        <span><span className="map-legend-dot map-legend-dot--visited" />Visited</span>
        <span><span className="map-legend-dot map-legend-dot--unvisited" />Not yet</span>
        <span className="map-country-count">{visited.length} / {WORLD_COUNTRY_COUNT} countries</span>
      </div>
    </div>
  )
}

// ─── CONSTANTS ───────────────────────────────────────────────────────────────

const INTERESTS = [
  { id: "outdoor",         label: "Outdoor adventures",  icon: <Trees size={13} /> },
  { id: "cultural",        label: "Art & museums",        icon: <Landmark size={13} /> },
  { id: "food_and_drink",  label: "Food & drink",         icon: <Utensils size={13} /> },
  { id: "nightlife",       label: "Nightlife",            icon: <Music2 size={13} /> },
  { id: "shopping",        label: "Shopping",             icon: <ShoppingBag size={13} /> },
  { id: "wellness",        label: "Wellness",             icon: <Dumbbell size={13} /> },
  { id: "historical",      label: "History",              icon: <Camera size={13} /> },
  { id: "scenic",          label: "Scenic spots",         icon: <Heart size={13} /> },
  { id: "adventurous",     label: "Adventurous",          icon: <Mountain size={13} /> },
  { id: "family_friendly", label: "Family-friendly",      icon: <Users size={13} /> },
  { id: "romantic",        label: "Romantic",             icon: <Heart size={13} /> },
  { id: "pet_friendly",    label: "Pet-friendly",         icon: <PawPrint size={13} /> },
  { id: "upscale",         label: "Upscale",              icon: <Gem size={13} /> },
  { id: "budget_friendly", label: "Budget-friendly",      icon: <Wallet size={13} /> },
]

const CUISINES = [
  "American","Italian","East Asian","Southeast Asian",
  "Mexican/Latin American","Indian/South Asian",
  "Mediterranean/Middle Eastern","Vegetarian Focus","Seafood Focus",
]

const DIETARY = [
  "Vegetarian","Vegan","Gluten-free","Halal",
  "Kosher","Nut allergy","Dairy-free","None",
]

const BUDGET_LABELS = {
  "1":"Free / nearly free","2":"Budget-conscious","3":"Moderate","4":"Comfortable","5":"No limit",
}
const TRIP_BUDGET_LABELS = {
  "1":"Budget (< $500)","2":"Moderate ($500–$1,500)","3":"Comfortable ($1,500–$3,000)","4":"Luxury ($3,000+)","0":"Not applicable",
}

// ─── SHARE LINK ──────────────────────────────────────────────────────────────

function ShareLink({ username }) {
  const [copied, setCopied] = useState(false)
  const url = `planit.app/u/${username || "explorer"}`

  const handleCopy = () => {
    navigator.clipboard.writeText(`https://${url}`).catch(() => {})
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="share-link-row">
      <Link size={13} style={{ color: "var(--c-tag)", flexShrink: 0 }} />
      <span className="share-link-url">{url}</span>
      <button className={`share-copy-btn${copied ? " copied" : ""}`} onClick={handleCopy}>
        {copied ? <><Check size={11} /> Copied!</> : <><Copy size={11} /> Copy</>}
      </button>
    </div>
  )
}

// ─── PREFS EDITOR ────────────────────────────────────────────────────────────

function PrefsEditor({ prefs, onSave, onCancel }) {
  const [form, setForm] = useState({
    use_case: "", party_type: "", daily_budget_tier: "3", trip_budget_tier: "0",
    preferred_tags: [], exploration_score: 3, popularity_weight: 3,
    cuisine_preferences: [], dietary_restrictions: [], travel_mode: [],
    max_travel_minutes: "", itinerary_pace: "",
    ...prefs,
    daily_budget_tier: String(prefs?.daily_budget_tier ?? "3"),
    trip_budget_tier:  String(prefs?.trip_budget_tier  ?? "0"),
    travel_mode: Array.isArray(prefs?.travel_mode)
      ? prefs.travel_mode
      : prefs?.travel_mode ? [prefs.travel_mode] : [],
  })

  const set    = (k, v) => setForm(p => ({ ...p, [k]: v }))
  const toggle = (k, v) => setForm(p => ({
    ...p, [k]: p[k]?.includes(v) ? p[k].filter(x => x !== v) : [...(p[k] || []), v],
  }))
  const mode = form.travel_mode?.[0] ?? ""

  return (
    <div className="prefs-editor">
      <fieldset>
        <legend>1 · What do you use PlanIt for?</legend>
        <div className="pref-radio-group">
          {[["local","Local"],["daytrip","Day trips"],["travel","Long trips"],["mixed","All"]].map(([v,l]) => (
            <label key={v} className={form.use_case === v ? "active" : ""}>
              <input type="radio" checked={form.use_case === v} onChange={() => set("use_case", v)} />{l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>2 · Traveling as</legend>
        <div className="pref-radio-group">
          {[["solo","Solo"],["couple","Couple"],["friends","Friends"],["family","Family"],["mixed","Mixed"]].map(([v,l]) => (
            <label key={v} className={form.party_type === v ? "active" : ""}>
              <input type="radio" checked={form.party_type === v} onChange={() => set("party_type", v)} />{l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>3 · Daily budget — {BUDGET_LABELS[form.daily_budget_tier]}</legend>
        <input type="range" min="1" max="5" value={form.daily_budget_tier}
          onChange={e => set("daily_budget_tier", e.target.value)} className="pref-slider" />
      </fieldset>

      <fieldset>
        <legend>4 · Long-trip budget</legend>
        <div className="pref-radio-group">
          {[["1","< $500"],["2","$500–$1,500"],["3","$1,500–$3,000"],["4","$3,000+"],["0","N/A"]].map(([v,l]) => (
            <label key={v} className={form.trip_budget_tier === v ? "active" : ""}>
              <input type="radio" checked={form.trip_budget_tier === v} onChange={() => set("trip_budget_tier", v)} />{l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>5 · Activities &amp; interests</legend>
        <div className="pref-check-group">
          {INTERESTS.map(i => (
            <label key={i.id} className={form.preferred_tags?.includes(i.id) ? "active" : ""}>
              <input type="checkbox" checked={form.preferred_tags?.includes(i.id)}
                onChange={() => toggle("preferred_tags", i.id)} />
              <span className="chip-icon">{i.icon}</span>{i.label}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>6 · Openness to new places ({form.exploration_score}/5)</legend>
        <input type="range" min="1" max="5" value={form.exploration_score}
          onChange={e => set("exploration_score", Number(e.target.value))} className="pref-slider" />
        <span className="slider-label">
          {["","Stick to what I know","Mostly familiar","Balanced","Lean adventurous","Always new"][form.exploration_score]}
        </span>
      </fieldset>

      <fieldset>
        <legend>7 · Importance of popularity ({form.popularity_weight}/5)</legend>
        <input type="range" min="1" max="5" value={form.popularity_weight}
          onChange={e => set("popularity_weight", Number(e.target.value))} className="pref-slider" />
        <span className="slider-label">
          {["","Hidden gems only","Mostly hidden","Mix","Lean popular","Trending spots"][form.popularity_weight]}
        </span>
      </fieldset>

      <fieldset>
        <legend>8 · Preferred cuisines</legend>
        <div className="pref-check-group">
          {CUISINES.map(c => (
            <label key={c} className={form.cuisine_preferences?.includes(c) ? "active" : ""}>
              <input type="checkbox" checked={form.cuisine_preferences?.includes(c)}
                onChange={() => toggle("cuisine_preferences", c)} />{c}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>9 · Dietary restrictions</legend>
        <div className="pref-check-group">
          {DIETARY.map(d => (
            <label key={d} className={form.dietary_restrictions?.includes(d) ? "active" : ""}>
              <input type="checkbox" checked={form.dietary_restrictions?.includes(d)}
                onChange={() => toggle("dietary_restrictions", d)} />{d}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>10 · How do you get around?</legend>
        <div className="pref-radio-group">
          {[["walk","Walking"],["bike","Biking"],["transit","Public Transit"],["drive","Driving"],["other","Other"]].map(([v,l]) => (
            <label key={v} className={mode === v ? "active" : ""}>
              <input type="radio" checked={mode === v} onChange={() => set("travel_mode", [v])} />{l}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>11 · How far are you willing to travel?</legend>
        <div className="pref-radio-group">
          {["<10 min","10-20 min","20-40 min",">40 min"].map(v => (
            <label key={v} className={form.max_travel_minutes === v ? "active" : ""}>
              <input type="radio" checked={form.max_travel_minutes === v}
                onChange={() => set("max_travel_minutes", v)} />{v}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>12 · Preferred pace</legend>
        <div className="pref-radio-group">
          {["packed","balanced","relaxed"].map(v => (
            <label key={v} className={form.itinerary_pace === v ? "active" : ""}>
              <input type="radio" checked={form.itinerary_pace === v}
                onChange={() => set("itinerary_pace", v)} />
              {v.charAt(0).toUpperCase() + v.slice(1)}
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

// ─── PREFS SUMMARY ───────────────────────────────────────────────────────────

function PrefsSummary({ prefs }) {
  const mode = Array.isArray(prefs.travel_mode) ? prefs.travel_mode[0] : prefs.travel_mode
  const rows = [
    { label: "Use Case",   val: prefs.use_case },
    { label: "Group",      val: prefs.party_type },
    { label: "Daily $",    val: BUDGET_LABELS[String(prefs.daily_budget_tier)] },
    { label: "Trip $",     val: TRIP_BUDGET_LABELS[String(prefs.trip_budget_tier)] },
    { label: "Explore",    val: prefs.exploration_score != null ? `${prefs.exploration_score}/5` : null },
    { label: "Popularity", val: prefs.popularity_weight != null ? `${prefs.popularity_weight}/5` : null },
    { label: "Mode",       val: mode },
    { label: "Distance",   val: prefs.max_travel_minutes },
    { label: "Pace",       val: prefs.itinerary_pace },
  ].filter(r => r.val)

  return (
    <div className="prefs-summary">
      {rows.map(r => (
        <div className="pref-row" key={r.label}>
          <span className="pref-label">{r.label}</span>
          <span className="pref-val">{r.val}</span>
        </div>
      ))}
      {prefs.preferred_tags?.length > 0 && (
        <div className="pref-row pref-row--tags">
          <span className="pref-label">Interests</span>
          <div className="pref-tags">
            {prefs.preferred_tags.map(t => <span key={t} className="pref-tag">{t.replaceAll("_"," ")}</span>)}
          </div>
        </div>
      )}
      {prefs.cuisine_preferences?.length > 0 && (
        <div className="pref-row pref-row--tags">
          <span className="pref-label">Cuisines</span>
          <div className="pref-tags">
            {prefs.cuisine_preferences.map(c => <span key={c} className="pref-tag">{c}</span>)}
          </div>
        </div>
      )}
      {prefs.dietary_restrictions?.length > 0 && (
        <div className="pref-row pref-row--tags">
          <span className="pref-label">Dietary</span>
          <div className="pref-tags">
            {prefs.dietary_restrictions.map(d => <span key={d} className="pref-tag">{d}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── PROFILE PAGE ────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const navigate     = useNavigate()
  const fileInputRef = useRef(null)
  const { user } = useAuth()

  const [name, setName] = useState(() => localStorage.getItem("userName") || user?.name || "")
  const [bio,  setBio]  = useState(() => localStorage.getItem("userBio")  || "Not all who wander are lost.")  
  const [avatar, setAvatar] = useState(() => localStorage.getItem("userAvatar") || null)
  const [identityDirty, setIdentityDirty] = useState(false)
  const [visited, setVisited] = useState(() => {
    try { return JSON.parse(localStorage.getItem("visitedCountries") || "[]") }
    catch { return [] }
  })
  const [countryMeta, setCountryMeta] = useState([])
  const toggleCountry = useCallback((iso2) => {
    if (!iso2) return
    setVisited(prev =>
      prev.includes(iso2) ? prev.filter(c => c !== iso2) : [...prev, iso2]
    )
  }, [])

  const [editingPrefs, setEditingPrefs] = useState(false)
  const [prefs, setPrefs] = useState(() => {
    try { return JSON.parse(localStorage.getItem("userPreferences") || "null") }
    catch { return null }
  })

  const savePrefs = (updated) => {
    localStorage.setItem("userPreferences", JSON.stringify(updated))
    setPrefs(updated)
    setEditingPrefs(false)
  }

  const handleAvatarClick  = () => fileInputRef.current?.click()
  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => setAvatar(ev.target.result)
    reader.readAsDataURL(file)
  }

  const handleSaveIdentity = () => setIdentityDirty(false)

  // If users log in from the same device, the info stays the same so this is good for demo purposes only
  // There will be issues generating if user clicks signout so DON'T CLICK IT
  const handleSignOut = () => {
    localStorage.clear()
    // localStorage.removeItem("token")
    // localStorage.removeItem("currentUser")
    navigate("/")
  }

  const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()
  
  useEffect(() => { localStorage.setItem("userName", name) }, [name])
  
  useEffect(() => { localStorage.setItem("userBio",  bio)  }, [bio])
  
  useEffect(() => {
    if (avatar) localStorage.setItem("userAvatar", avatar)
    else localStorage.removeItem("userAvatar")
  }, [avatar])

  useEffect(() => {
    if (user?.name && !localStorage.getItem("userName")) {
      setName(user.name)
    }
  }, [user])

  useEffect(() => {
    localStorage.setItem("visitedCountries", JSON.stringify(visited))
  }, [visited])
  return (
    <div className="page">
      <div className="profile-container">

        {/* ── HEADER ── */}
        <div className="profile__header">
          <div className="profile__avatar-wrap" onClick={handleAvatarClick}>
            <div className="profile__avatar">
              {avatar ? <img src={avatar} alt="avatar" /> : initials}
            </div>
            <div className="profile__avatar-overlay">
              <Camera size={15} />
              Change
            </div>
            <input ref={fileInputRef} type="file" accept="image/*"
              style={{ display:"none" }} onChange={handleAvatarChange} />
          </div>

          <div className="profile__bio-wrap">
            <input
              className="profile__name-input"
              value={name}
              onChange={e => { setName(e.target.value); setIdentityDirty(true) }}
              placeholder="Your name"
            />
            <textarea
              className="profile__bio-input"
              value={bio}
              rows={1}
              onChange={e => { setBio(e.target.value); setIdentityDirty(true) }}
              placeholder="Add a travel bio…"
            />
            <span className="profile__edit-hint">Click to edit</span>
            <span className="profile__badge">Explorer</span>
          </div>

          <div className="profile__stats">
            {[
              { v: visited.length, l: "Countries", max: WORLD_COUNTRY_COUNT },
              { v: 20,  l: "Trips",   max: 50  },
              { v: 0,  l: "Days",    max: 365 },
              { v: 3,   l: "Friends", max: 10  },
            ].map(({ v, l, max }) => (
              <div className="profile__stat" key={l}>
                <span>{v}</span>
                <small>{l}</small>
                <div className="stat-bar">
                  <div style={{ width: `${Math.min((v / max) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>

          <div className="profile__header-actions">
            {identityDirty && (
              <button className="btn btn--primary profile__save-btn" onClick={handleSaveIdentity}>
                <Save size={13} style={{ marginRight: 4 }} /> Save
              </button>
            )}
            <button className="btn btn--danger" onClick={handleSignOut}>
              <LogOut size={14} /> Sign out
            </button>
          </div>
        </div>

        {/* ── BODY ── */}
        <div className="profile__body">

          <div className="profile__col">
            <div className="profile__section-header">
              <h3>My Preferences</h3>
              <span onClick={() => setEditingPrefs(!editingPrefs)}>
                {editingPrefs ? "Cancel" : "Edit"}
              </span>
            </div>
            {!editingPrefs && prefs  && <PrefsSummary prefs={prefs} />}
            {!editingPrefs && !prefs && <p className="profile__pref-hint">No preferences saved yet.</p>}
            {editingPrefs && (
              <PrefsEditor prefs={prefs || {}} onSave={savePrefs} onCancel={() => setEditingPrefs(false)} />
            )}
          </div>

          <div className="profile__col">
            <div className="profile__section-header">
              <h3>Countries Visited</h3>
              <span onClick={() => setVisited([])}>Clear all</span>
            </div>
            <WorldMap visited={visited} onToggle={toggleCountry} onFeaturesLoaded={setCountryMeta} />
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "12px", maxHeight: "200px", overflowY: "auto" }}>
              {countryMeta.map(({ iso2, name }) => (
                <button
                  key={iso2}
                  onClick={() => toggleCountry(iso2)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "999px",
                    fontSize: "12px",
                    cursor: "pointer",
                    background: visited.includes(iso2) ? "rgba(0,217,255,0.2)" : "transparent",
                    border: visited.includes(iso2) ? "1px solid rgba(103,211,255,0.6)" : "1px solid rgba(255,255,255,0.15)",
                    color: visited.includes(iso2) ? "rgb(103,211,255)" : "rgba(255,255,255,0.5)",
                  }}
                >
                  {name}
                </button>
              ))}
            </div>
            <p className="profile__pref-hint">
              Click any country to mark it as visited. Drag to pan, use +/− to zoom.
            </p>
          </div>

        </div>
      </div>
    </div>
  )
}