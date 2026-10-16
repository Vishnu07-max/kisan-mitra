import api from './api'

export const listFarms = () => api.get('/farms/').then((res) => res.data)
export const createFarm = (data) => api.post('/farms/', data).then((res) => res.data)
export const updateFarm = (id, data) => api.patch(`/farms/${id}/`, data).then((res) => res.data)
export const deleteFarm = (id) => api.delete(`/farms/${id}/`)