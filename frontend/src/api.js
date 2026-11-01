// Thin fetch wrapper for the FastAPI backend.
export async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${text}`)
  }
  return res.json()
}
