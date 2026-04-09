export default function DestinationPage() {
  const destinations = [
    { name: 'Paris, France', emoji: '🇫🇷', desc: 'The City of Light' },
    { name: 'Tokyo, Japan', emoji: '🇯🇵', desc: 'Modern meets tradition' },
    { name: 'New York, USA', emoji: '🗽', desc: 'The city that never sleeps' },
    { name: 'Barcelona, Spain', emoji: '🇪🇸', desc: 'Art and architecture' },
  ]

  return (
    <div className="page">
      <h1>Discover Destinations</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px', padding: '16px' }}>
        {destinations.map((dest) => (
          <div key={dest.name} style={{ padding: '16px', background: '#f0f0f0', borderRadius: '8px', cursor: 'pointer' }}>
            <div style={{ fontSize: '32px' }}>{dest.emoji}</div>
            <h3>{dest.name}</h3>
            <p>{dest.desc}</p>
            <button style={{ padding: '8px 12px', background: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Explore</button>
          </div>
        ))}
      </div>
    </div>
  )
}