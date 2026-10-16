// Converts an axios error into { type, fields }.
// type is used to pick a translated message; fields holds per-field backend messages.
export function getErrorInfo(err) {
  if (!err.response) return { type: 'network', fields: {} }

  const status = err.response.status
  const details = err.response.data?.error?.details || {}
  const fields = {}

  if (typeof details === 'object') {
    for (const [key, value] of Object.entries(details)) {
      fields[key] = Array.isArray(value) ? value.join(' ') : String(value)
    }
  }

  let type = 'server'
  if (status === 401) type = 'credentials'
  else if (status === 429) type = 'throttled'
  else if (status === 400) type = 'validation'

  return { type, fields }
}