import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('gym_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('gym_token')
      localStorage.removeItem('gym_member_name')
      localStorage.removeItem('gym_member_id')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const login = (username, password) =>
  api.post('/auth/member/login', { username, password })

export const getProfile = () => api.get('/member/me')
export const getAttendance = () => api.get('/member/attendance?limit=30')
export const sendChat = (message) => api.post('/chat', { message })

export default api
