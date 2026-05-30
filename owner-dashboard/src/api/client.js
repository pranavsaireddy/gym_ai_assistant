import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('staff_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('staff_token')
      localStorage.removeItem('staff_name')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const staffLogin = (username, password) =>
  api.post('/auth/staff/login', { username, password })

export const getDashboard = () => api.get('/admin/dashboard')
export const getMembers = (params) => api.get('/admin/members', { params })
export const getDropout = (threshold = 0.5) => api.get(`/admin/dropout?threshold=${threshold}`)
export const getRevenue = (months = 6) => api.get(`/admin/revenue?months=${months}`)
export const getCookieHealth = () => api.get('/health/cookies')
export const sendChat = (message) => api.post('/chat', { message })

export const syncMembers = () => api.post('/admin/sync/members')
export const syncStatus = () => api.post('/admin/sync/status')
export const syncBilling = () => api.post('/admin/sync/billing')
export const syncAll = () => api.post('/admin/sync/all')

export default api
