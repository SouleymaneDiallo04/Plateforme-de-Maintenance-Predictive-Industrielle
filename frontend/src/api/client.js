import axios from 'axios'

const API_BASE = 'http://localhost:8001/api'

export const api = axios.create({
    baseURL: API_BASE,
    timeout: 10000,
})

export const WS_URL = 'ws://localhost:8001/api'

// ── Authentification JWT ──────────────────────────────────────────────────────

function parseJwt(token) {
    try {
        const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
        return JSON.parse(atob(base64))
    } catch {
        return null
    }
}

export const auth = {
    getToken : () => localStorage.getItem('prognosense_token') || '',
    setToken : (t) => {
        if (t) localStorage.setItem('prognosense_token', t)
        else   localStorage.removeItem('prognosense_token')
    },
    getUser  : () => {
        const raw = localStorage.getItem('prognosense_user')
        try { return raw ? JSON.parse(raw) : null } catch { return null }
    },
    setUser  : (u) => {
        if (u) localStorage.setItem('prognosense_user', JSON.stringify(u))
        else   localStorage.removeItem('prognosense_user')
    },
    getRole  : () => {
        const user = auth.getUser()
        if (user?.role) return user.role
        // fallback : décoder le JWT
        const token = auth.getToken()
        if (!token) return null
        const payload = parseJwt(token)
        return payload?.role || null
    },
    isExpired: () => {
        const token = auth.getToken()
        if (!token) return true
        const payload = parseJwt(token)
        if (!payload?.exp) return true
        return Date.now() / 1000 > payload.exp
    },
    logout   : () => {
        auth.setToken(null)
        auth.setUser(null)
    },
}

// Intercepteur : ajoute Authorization sur chaque requête si token valide
api.interceptors.request.use(cfg => {
    const token = auth.getToken()
    if (token && !auth.isExpired()) {
        cfg.headers['Authorization'] = `Bearer ${token}`
    }
    return cfg
})

// ── Endpoints ──────────────────────────────────────────────────────────────
export const endpoints = {
    // Flotte
    fleet           : ()           => api.get('/fleet'),
    machine         : (id)         => api.get(`/machine/${id}`),
    machineHistory  : (id)         => api.get(`/machine/${id}/history`),
    machineDiagnose : (id, data)   => api.post(`/machine/${id}/diagnose`, data),

    // Benchmark
    benchmark   : ()           => api.get('/benchmark'),
    activeModel : (ds)         => api.get(`/model/active/${ds}`),
    selectModel : (ds, model)  =>
        api.post(`/model/select?dataset=${ds}&model_name=${encodeURIComponent(model)}`),

    // Alertes
    alerts: () => api.get('/alerts'),

    // KPIs
    kpi      : (id) => api.get(`/kpi/${id}`),
    fleetKpi : ()   => api.get('/kpi/fleet/overview'),

    // Analyse spectrale
    indicators   : (data) => api.post('/signal/indicators', data),
    spectrum     : (data) => api.post('/signal/spectrum', data),
    diagnose     : (data) => api.post('/signal/diagnose', data),
    bearingFreqs : (data) => api.post('/bearing/frequencies', data),

    // Simulation
    simUnits   : ()               => api.get('/simulation/units'),
    simControl : (action, speed)  =>
        api.post(`/simulation/control?action=${action}&speed=${speed}`),

    // Injection
    injectFault   : (data) => api.post('/inject/fault', data),
    stopInjection : ()     => api.post('/inject/stop'),

    // Réentraînement
    retrainStart  : (data) => api.post('/retrain/start', data),
    retrainDemo   : (data) => api.post('/retrain/demo', data),
    retrainStatus : ()     => api.get('/retrain/status'),

    // Copilot (LLM : réponses parfois longues → délai d'attente élargi à 60 s)
    copilotChat   : (data) => api.post('/copilot/chat', data, { timeout: 60000 }),
    copilotReport : (id)   => api.post(`/copilot/report/${id}`, null, { timeout: 60000 }),

    // Export
    exportReport    : (id) => `${API_BASE}/export/report/${id}`,
    exportBenchmark : ()   => `${API_BASE}/export/benchmark`,

    // Docs
    faultGuide      : () => api.get('/docs/fault-guide'),
    indicatorsGuide : () => api.get('/docs/indicators-guide'),

    // Config
    config       : ()     => api.get('/config'),
    updateConfig : (data) => api.post('/config/update', data),

    // Drift & fiabilité modèles
    driftStatus       : ()        => api.get('/drift/status'),
    modelReliability  : (dataset) => api.get(`/model/reliability/${dataset}`),

    // Explainabilité SHAP
    explainShap        : (data)    => api.post('/explain/shap', data),
    featureImportance  : (dataset) => api.get(`/explain/feature-importance/${dataset}`),
    reliabilityDiagram : (data)    => api.post('/explain/reliability', data),
    calibrationStats   : (dataset) => api.get(`/explain/calibration/${dataset}`),

    // Audit trail
    auditRecent : (n = 100, machine_id = null) =>
        api.get('/audit/recent', { params: { n, ...(machine_id ? { machine_id } : {}) } }),
    auditStats  : () => api.get('/audit/stats'),

    // Analyse d'ordre
    orderSpectrum : (data) => api.post('/signal/order-spectrum', data),

    // Événements de maintenance & KPIs réels
    createMaintenanceEvent : (data)      => api.post('/maintenance/event', data),
    maintenanceEvents      : (id)        => api.get(`/maintenance/events/${id}`),
    kpiReal                : (id, days)  => api.get(`/kpi/real/${id}`, { params: days ? { days } : {} }),
    kpiRoi                 : (id)        => api.get(`/kpi/roi/${id}`),
    machineHistoryDB       : (id, hours) => api.get(`/machine/${id}/history/db`, { params: hours ? { hours } : {} }),

    // Analytics — efficacité prédictive
    predictionAccuracy : (id) => api.get(`/analytics/prediction-accuracy/${id}`),
    fleetReport        : ()   => api.get('/analytics/fleet-report'),

    // Versioning des modèles
    modelVersions  : (ds, model)          => api.get(`/model/versions/${ds}/${encodeURIComponent(model)}`),
    modelRollback  : (ds, model, version) => api.post(`/model/rollback?dataset=${ds}&model_name=${encodeURIComponent(model)}&version=${version}`),

    // Ensemble d'anomalie + replay signal
    ensembleDemo   : (ds)       => api.get(`/anomaly/ensemble/demo/${ds}`),
    replaySignal   : (ds, idx)  => api.get(`/replay/${ds}/${idx}`),

    // Sévérité ISO 10816/20816
    isoSeverity    : (data)     => api.post('/signal/iso-severity', data),

    // Ingestion temps réel + baseline machine
    ingestSignal      : (data)  => api.post('/ingest/signal', data),
    baselineFinalize  : (id)    => api.post(`/ingest/baseline/finalize?machine_id=${encodeURIComponent(id)}`),
    baselineReset     : (id)    => api.post(`/ingest/baseline/reset?machine_id=${encodeURIComponent(id)}`),
    baselineStatus    : ()      => api.get('/ingest/baseline/status'),

    // Ordres de travail (GMAO closed-loop)
    workOrders        : (params) => api.get('/workorders', { params: params || {} }),
    createWorkOrder   : (data)   => api.post('/workorder', data),
    updateWorkOrder   : (id, status) => api.patch(`/workorder/${id}`, { status }),
    workOrdersConfig  : ()       => api.get('/workorders/config'),

    // Human-in-the-loop (verdict + fausses alarmes)
    persistedAlerts   : (machine_id) => api.get('/alerts/persisted', { params: machine_id ? { machine_id } : {} }),
    setAlertVerdict   : (alertId, data) => api.post(`/alerts/${alertId}/verdict`, data),
    falseAlarmRate    : (machine_id) => api.get('/analytics/false-alarm-rate', { params: machine_id ? { machine_id } : {} }),
}
