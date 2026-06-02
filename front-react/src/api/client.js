import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
})

export const getCommunes = () => api.get('/api/communes').then(r => r.data)
export const getAnnees   = () => api.get('/api/annees').then(r => r.data)
export const getStats    = (commune) => api.get('/api/stats', { params: { commune } }).then(r => r.data)
export const getBiens    = (params)  => api.get('/api/biens', { params }).then(r => r.data)
export const getCarte = (params) => api.get('/api/carte', { params }).then(r => r.data)