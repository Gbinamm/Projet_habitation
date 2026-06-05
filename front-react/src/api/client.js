import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
})

export const getCommunes = () => api.get('/api/communes').then(r => r.data)
export const getAnnees   = () => api.get('/api/annees').then(r => r.data)
export const getStats    = (commune, annee = 0) => api.get('/api/stats', { params: { commune, annee } }).then(r => r.data)
export const getBiens    = (params)  => api.get('/api/biens', { params }).then(r => r.data)
export const getCarte    = (params)  => api.get('/api/carte', { params }).then(r => r.data)

export const getGeoJson       = ()       => api.get('/api/geojson').then(r => r.data)
export const getCarteCommune  = (params) => api.get('/api/carte/commune', { params }).then(r => r.data)