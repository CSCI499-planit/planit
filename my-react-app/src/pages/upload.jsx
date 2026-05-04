import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../components/upload.css";

function isGoogleTakeoutFile(data) {
  if (data.timelineObjects) return true;
  if (Array.isArray(data.features) && data.features.length > 0) {
    const props = data.features[0]?.properties || {};
    if ("five_star_rating_published" in props) return true; // Reviews
    if ("Title" in props || "location" in props) return true; // Saved Places
  }
  return false;
}

export default function UploadPage() {
  const navigate = useNavigate();

  const [files, setFiles] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleFileChange = async (e) => {
    setError("");
    const selected = Array.from(e.target.files);

    const nonJson = selected.filter((f) => !f.name.endsWith(".json"));
    if (nonJson.length > 0) {
      setError(
        `Only .json files are accepted: ${nonJson.map((f) => f.name).join(", ")}`,
      );
      e.target.value = "";
      return;
    }

    // validate each file is a recognised Google Takeout format
    const invalid = [];
    for (const f of selected) {
      try {
        const text = await f.text();
        const data = JSON.parse(text);
        if (!isGoogleTakeoutFile(data)) invalid.push(f.name);
      } catch {
        invalid.push(f.name);
      }
    }

    if (invalid.length > 0) {
      setError(`Not recognised as Google Takeout files: ${invalid.join(", ")}`);
      e.target.value = "";
      return;
    }

    setFiles(selected);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (files.length === 0) {
      setError("Please select at least one file.");
      return;
    }

    setLoading(true);

    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/import/google-takeout`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${sessionStorage.getItem("access_token")}`,
          },
          body: formData,
        },
      );

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail ?? "Upload failed.");
        return;
      }

      setResult(data);
    } catch {
      setError("Upload failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

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
                Go to{" "}
                <a
                  href="https://takeout.google.com"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Google Takeout
                </a>
              </li>
              <li>Click "Deselect all"</li>
              <li>
                Select only <strong>Maps (your places)</strong>
              </li>
              <li>Create export, download the ZIP, and extract it</li>
              <li>
                From the extracted folder, upload: <strong>Reviews.json</strong>{" "}
                and <strong>Saved Places.json</strong> (multiselect)
              </li>
            </ol>
          </div>

          {result ? (
            <div className="upload-result">
              {result.imported === 0 ? (
                <p className="result-empty">
                  No places were found. Make sure you uploaded the right files
                  from your Takeout export.
                </p>
              ) : (
                <>
                  <p className="result-success">
                    {result.imported} place{result.imported !== 1 ? "s" : ""}{" "}
                    imported from your Maps history
                  </p>
                  <ul className="result-breakdown">
                    {result.sources.timeline > 0 && (
                      <li>{result.sources.timeline} from Location History</li>
                    )}
                    {result.sources.reviews > 0 && (
                      <li>{result.sources.reviews} from Reviews</li>
                    )}
                    {result.sources.saved > 0 && (
                      <li>{result.sources.saved} from Saved Places</li>
                    )}
                  </ul>
                </>
              )}
              <button
                className="btn btn--primary"
                onClick={() => navigate("/app/home")}
              >
                Continue
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="upload-form">
              <input
                type="file"
                accept=".json"
                multiple
                onChange={handleFileChange}
              />

              {files.length > 0 && (
                <ul className="file-name">
                  {files.map((f) => (
                    <li key={f.name}>{f.name}</li>
                  ))}
                </ul>
              )}

              {error && <div className="error-message">{error}</div>}

              <div className="upload-actions">
                <button
                  type="submit"
                  className="btn btn--primary"
                  disabled={loading}
                >
                  {loading ? "Uploading..." : "Upload"}
                </button>
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => navigate("/app/home")}
                >
                  Skip
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
