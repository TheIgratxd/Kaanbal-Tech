const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:3001')
  .replace(/\/$/, '')
const AI_BASE_URL = (import.meta.env.VITE_AI_API_URL || 'http://localhost:8000')
  .replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function getErrorMessage(body, status) {
  const message = body?.message ?? body?.detail
  if (Array.isArray(message)) return message.join('. ')
  if (typeof message === 'string' && message.trim()) return message
  if (typeof body === 'string' && body.trim()) return body
  return `La solicitud falló (HTTP ${status}).`
}

async function requestJson(baseUrl, path, options = {}) {
  const {
    method = 'GET',
    body,
    token,
    headers = {},
    timeoutMs = 15000,
  } = options
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  const requestHeaders = new Headers(headers)

  if (body !== undefined && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }
  if (token) requestHeaders.set('Authorization', `Bearer ${token}`)

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
    const rawBody = await response.text()
    let responseBody = null

    if (rawBody) {
      try {
        responseBody = JSON.parse(rawBody)
      } catch {
        responseBody = rawBody
      }
    }

    if (!response.ok) {
      if (response.status === 401 && token) {
        window.dispatchEvent(new Event('kaanbal:unauthorized'))
      }
      throw new ApiError(
        getErrorMessage(responseBody, response.status),
        response.status,
        responseBody,
      )
    }

    return responseBody
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (controller.signal.aborted) {
      throw new Error('La solicitud tardó demasiado. Inténtalo de nuevo.')
    }
    throw new Error(
      'No fue posible conectar con el servicio. Verifica que esté disponible.',
      { cause: error },
    )
  } finally {
    clearTimeout(timeout)
  }
}

export function api(path, options = {}) {
  return requestJson(API_BASE_URL, path, options)
}

export function tutorApi(path, options = {}) {
  return requestJson(AI_BASE_URL, path, {
    timeoutMs: 120000,
    ...options,
  })
}
