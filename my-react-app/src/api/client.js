export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

function requireApiBaseUrl() {
  if (!apiBaseUrl) {
    throw new Error('Missing VITE_API_BASE_URL. Set it to the deployed backend URL.')
  }

  return apiBaseUrl
}

export function apiUrl(path) {
  return `${requireApiBaseUrl()}${path}`
}

function getToken() {
  return sessionStorage.getItem('access_token')
}

async function request(path, { body, method, ...options } = {}) {
  const token = getToken()

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const res = await fetch(apiUrl(path), {
    method: method ?? (body ? 'POST' : 'GET'),
    headers,
    ...(body ? { body: JSON.stringify(body) } : {}),
    ...options,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(err.detail ?? 'Request failed'), { status: res.status })
  }

  return res.json()
}

export const api = {
  get:    (path, options)       => request(path, { method: 'GET', ...options }),
  post:   (path, body, options) => request(path, { method: 'POST', body, ...options }),
  put:    (path, body, options) => request(path, { method: 'PUT', body, ...options }),
  delete: (path, options)       => request(path, { method: 'DELETE', ...options }),
}
