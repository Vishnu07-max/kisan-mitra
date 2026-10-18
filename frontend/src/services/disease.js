import api from './api'

// The first prediction loads the model on the server, so allow a long timeout.
export const predict = (file, farmId) => {
  const form = new FormData()
  form.append('image', file)
  if (farmId) form.append('farm_id', farmId)
  return api.post('/disease/predict/', form, { timeout: 90000 }).then((res) => res.data)
}

export const listAssessments = (page = 1) =>
  api.get('/disease/assessments/', { params: { page } }).then((res) => res.data)

export const deleteAssessment = (id) => api.delete(`/disease/assessments/${id}/`)

// Photos are private: fetch them with the login token, not through a public URL.
// The API gives paths like /api/v1/..., but our axios baseURL already ends in /api/v1.
export const fetchImageBlob = (url) =>
  api.get(url.replace(/^\/api\/v1/, ''), { responseType: 'blob' }).then((res) => res.data)