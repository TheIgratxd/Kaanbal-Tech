const API = 'http://localhost:3000'

export async function api(path, options = {}) {
  const token = localStorage.getItem('access_token')

  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })

  if (res.status === 401) {
    localStorage.removeItem('access_token')
    window.location.href = '/login'
    throw new Error('Sesión expirada')
  }

  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.message || 'Error')
  return body
}