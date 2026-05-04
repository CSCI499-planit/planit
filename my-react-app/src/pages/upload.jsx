import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../components/upload.css'

export default function UploadPage() {
  const navigate = useNavigate()

  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]

    if (!selectedFile.name.endsWith('.json')) {
      setError('Please upload a JSON file.')
      return
    }

    setFile(selectedFile)
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!file) {
      setError('Please select a file.')
      return
    }

    setLoading(true)

    const formData = new FormData()
    formData.append('file', file)

    try {
      await fetch(`${import.meta.env.VITE_API_BASE_URL}/imports/google-takeout`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sessionStorage.getItem('access_token')}`
        },
        body: formData
      })

      navigate('/app/home')
    } catch {
      setError('Upload failed.')
    }

    setLoading(false)
  }

  return (
    <div className="upload-page">
      <div className="upload-container">

        <div className="upload-header">
          <h1>Upload Google Maps History</h1>
          <p>Get better travel recommendations</p>
        </div>

        <div className="upload-content">

          <div className="upload-info">
            <h3>How to get your data:</h3>

            <ol>
              <li>
                Go to{' '}
                <a
                  href="https://takeout.google.com"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Google Takeout
                </a>
              </li>

              <li>Click “Deselect all”</li>

              <li>Select:
                <ul>
                  <li>Maps</li>
                  <li>Location History</li>
                  <li>Saved</li>
                </ul>
              </li>

              <li>Create export and download the ZIP file</li>

              <li>Extract the ZIP and upload the JSON file here</li>
            </ol>
          </div>

          <form onSubmit={handleSubmit} className="upload-form">

            <input
              type="file"
              accept=".json"
              onChange={handleFileChange}
            />

            {file && (
              <p className="file-name">{file.name}</p>
            )}

            {error && (
              <div className="error-message">{error}</div>
            )}

            <div className="upload-actions">

              <button
                type="submit"
                className="btn btn--primary"
                disabled={loading}
              >
                {loading ? 'Uploading...' : 'Upload'}
              </button>

              <button
                type="button"
                className="btn btn--secondary"
                onClick={() => navigate('/app/home')}
              >
                Skip
              </button>

            </div>

          </form>

        </div>

      </div>
    </div>
  )
}