import { useEffect, useRef, useState, useCallback } from 'react'
import { WS_URL } from '../api/client'

export function useSimulationWS() {
    const ws         = useRef(null)
    const retryCount = useRef(0)
    const retryTimer = useRef(null)
    const [data,    setData]    = useState(null)
    const [status,  setStatus]  = useState('disconnected')
    const [history, setHistory] = useState([])

    const connect = useCallback(() => {
        if (ws.current?.readyState === WebSocket.OPEN) return

        // Annuler tout timer de retry en cours
        if (retryTimer.current) {
            clearTimeout(retryTimer.current)
            retryTimer.current = null
        }

        setStatus('connecting')
        ws.current = new WebSocket(`${WS_URL}/ws/simulation`)

        ws.current.onopen = () => {
            setStatus('connected')
            retryCount.current = 0
            ws.current.send(JSON.stringify({ action: 'play' }))
        }

        ws.current.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data)
                if (msg.type === 'cycle_update') {
                    setData(msg)
                    setHistory(prev => {
                        const features = msg.features || {}
                        const entry = {
                            cycle        : msg.cycle,
                            health_index : msg.health_index,
                            rul_pred     : msg.rul_pred,
                            rul_true     : msg.rul_true,
                            anomaly      : msg.anomaly_score,
                            status       : msg.status,
                            RMS          : features.RMS          ?? null,
                            Kurtosis     : features.Kurtosis     ?? null,
                            Crest_Factor : features.Crest_Factor ?? null,
                            Peak_to_Peak : features.Peak_to_Peak ?? null,
                            Skewness     : features.Skewness     ?? null,
                            Std          : features.Std          ?? null,
                        }
                        return [...prev, entry].slice(-200)
                    })
                }
            } catch (err) {
                console.error('WS parse error:', err)
            }
        }

        ws.current.onclose = () => {
            setStatus('disconnected')
            // Retry exponentiel : 1s, 2s, 4s, 8s … plafonné à 30s
            const delay = Math.min(1000 * Math.pow(2, retryCount.current), 30000)
            retryCount.current += 1
            console.log(`WebSocket fermé — reconnexion dans ${delay}ms (essai ${retryCount.current})`)
            retryTimer.current = setTimeout(connect, delay)
        }

        ws.current.onerror = () => {
            setStatus('error')
            ws.current?.close()
        }
    }, [])

    const send = useCallback((msg) => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(msg))
        }
    }, [])

    const setSpeed  = useCallback((s) => send({ action: 'set_speed', speed: s }), [send])
    const pause     = useCallback(() => send({ action: 'pause' }), [send])
    const play      = useCallback(() => send({ action: 'play'  }), [send])
    const reset     = useCallback(() => {
        send({ action: 'reset' })
        setHistory([])
    }, [send])

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
            clearTimeout(retryTimer.current)
            ws.current?.close()
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
