import axios from 'axios'

// Backend address. Can be overridden later with VITE_API_URL for deployment.
const baseURL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1'

const api = axios.create({
  baseURL,
  timeout: 10000,
})

export default api