import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_URL } from '../api/client'

export function useSimulationWS() {
    const ws = useRef(null)
    const [data, setData] = useState(null)
    const [status, setStatus] = useState('disconnected')
    const [history, setHistory] = useState([])

    const connect = useCallback(() => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) return

        ws.current = new WebSocket(`${WS_URL}/ws/simulation`)

        ws.current.onopen = () => {
            setStatus('connected')
            if (ws.current) ws.current.send(JSON.stringify({ action: 'play' }))
        }

        ws.current.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data)
                if (msg.type === 'cycle_update') {
                    setData(msg)
                    setHistory(prev => {
                        const features = msg.features || {}
                        const entry = {
                            cycle: msg.cycle,
                            health_index: msg.health_index,
                            rul_pred: msg.rul_pred,
                            rul_true: msg.rul_true,
                            anomaly: msg.anomaly_score,
                            status: msg.status,
                            RMS: features.RMS !== undefined ? features.RMS : null,
                            Kurtosis: features.Kurtosis !== undefined ? features.Kurtosis : null,
                            Crest_Factor: features.Crest_Factor !== undefined ? features.Crest_Factor : null,
                            Peak_to_Peak: features.Peak_to_Peak !== undefined ? features.Peak_to_Peak : null,
                            Skewness: features.Skewness !== undefined ? features.Skewness : null,
                            Std: features.Std !== undefined ? features.Std : null,
                        }
                        return [...prev, entry].slice(-200)
                    })
                }
            } catch (err) {
                console.error('WS parse error:', err)
            }
        }

        ws.current.onclose = () => setStatus('disconnected')
        ws.current.onerror = () => setStatus('error')
    }, [])

    const send = useCallback((msg) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(msg))
        }
    }, [])

    const setSpeed = (s) => send({ action: 'set_speed', speed: s })
    const pause = () => send({ action: 'pause' })
    const play = () => send({ action: 'play' })
    const reset = () => {
        send({ action: 'reset' });
        setHistory([])
    }
    const setMachine = useCallback((machine_id, dataset, unit_id = null) => {
        setHistory([])
        send({
            action: 'set_machine',
            machine_id,
            dataset,
            ...(unit_id ? { unit_id } : {}),
        })
    }, [send])

    useEffect(() => {
        connect()
        return () => {
            if (ws.current) ws.current.close()
        }
    }, [connect])

    return {
        data,
        status,
        history,
        setSpeed,
        pause,
        play,
        reset,
        setMachine,
        connect,
        send,
    }
}