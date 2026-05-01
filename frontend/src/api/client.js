import axios from 'axios'

const API_BASE = 'http://localhost:8000/api'
const WS_BASE = 'ws://localhost:8000'

export const api = axios.create({
    baseURL: API_BASE,
    timeout: 10000,
})

export const WS_URL = 'ws://localhost:8000/api' // ou WS_BASE + '/api'

// ── Endpoints ──────────────────────────────────────────────
export const endpoints = {
    // Flotte
    fleet: () => api.get('/fleet'),
    machine: (id) => api.get(`/machine/${id}`),
    machineHistory: (id) => api.get(`/machine/${id}/history`),
    machineDiagnose: (id, data) => api.post(`/machine/${id}/diagnose`, data),

    // Benchmark
    benchmark: () => api.get('/benchmark'),
    activeModel: (ds) => api.get(`/model/active/${ds}`),
    selectModel: (ds, model) =>
        api.post(`/model/select?dataset=${ds}&model_name=${encodeURIComponent(model)}`),

    // Alertes
    alerts: () => api.get('/alerts'),

    // KPIs
    kpi: (id) => api.get(`/kpi/${id}`),
    fleetKpi: () => api.get('/kpi/fleet/overview'),

    // Analyse spectrale
    indicators: (data) => api.post('/signal/indicators', data),
    spectrum: (data) => api.post('/signal/spectrum', data),
    diagnose: (data) => api.post('/signal/diagnose', data),
    bearingFreqs: (data) => api.post('/bearing/frequencies', data),

    // Simulation
    simUnits: () => api.get('/simulation/units'),
    simControl: (action, speed) =>
        api.post(`/simulation/control?action=${action}&speed=${speed}`),

    // Injection
    injectFault: (data) => api.post('/inject/fault', data),
    stopInjection: () => api.post('/inject/stop'),

    // Réentraînement
    retrainStart: (data) => api.post('/retrain/start', data),
    retrainStatus: () => api.get('/retrain/status'),

    // Copilot
    copilotChat: (data) => api.post('/copilot/chat', data),
    copilotReport: (id) => api.post(`/copilot/report/${id}`),

    // Export
    exportReport: (id) => `${API_BASE}/export/report/${id}`,
    exportBenchmark: () => `${API_BASE}/export/benchmark`,

    // Docs
    faultGuide: () => api.get('/docs/fault-guide'),
    indicatorsGuide: () => api.get('/docs/indicators-guide'),

    // Config
    config: () => api.get('/config'),
    updateConfig: (data) => api.post('/config/update', data),
}