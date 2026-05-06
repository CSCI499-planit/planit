export default function ConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
    }}>
      <div style={{
        background: '#fff', borderRadius: 14, padding: '1.75rem 2rem',
        maxWidth: 340, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
        textAlign: 'center'
      }}>
        <p style={{ fontWeight: 600, color: '#0f172a', marginBottom: '0.4rem' }}>Are you sure?</p>
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1.5rem' }}>{message}</p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <button onClick={onCancel} style={{
            padding: '0.55rem 1.25rem', borderRadius: 8, border: '1.5px solid #e2e8f0',
            background: '#f8fafc', color: '#475569', fontWeight: 500, cursor: 'pointer', fontSize: '0.85rem'
          }}>Cancel</button>
          <button onClick={onConfirm} style={{
            padding: '0.55rem 1.25rem', borderRadius: 8, border: 'none',
            background: '#e11d48', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem'
          }}>Remove</button>
        </div>
      </div>
    </div>
  )
}