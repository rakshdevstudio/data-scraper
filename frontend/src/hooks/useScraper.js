import { useState, useEffect } from "react"
import API from "@/services/api"
import { toast } from "sonner"

export function useScraper() {
    const [status, setStatus] = useState("idle")
    const [metrics, setMetrics] = useState({ total: 0, done: 0, pending: 0, processing: 0, failed: 0 })
    const [logs, setLogs] = useState([])
    const [keywords, setKeywords] = useState([])

    // Polling for status and metrics (simpler than WS implementation for MVP stability)
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const statusRes = await API.get("/status")
                setStatus(statusRes.data.status)

                const metricsRes = await API.get("/metrics")
                setMetrics(metricsRes.data)

                // Only fetch latest logs
                const logsRes = await API.get("/logs?limit=50")
                setLogs(logsRes.data)
            } catch (e) {
                // Silent polling fail
            }
        }, 2000)
        return () => clearInterval(interval)
    }, [])

    const control = async (action) => {
        try {
            await API.post(`/control/${action}`)
            toast.success(`Scraper ${action} command sent`)
        } catch (e) {
            toast.error(`Failed to ${action} scraper`)
        }
    }

    const fetchKeywords = async () => {
        try {
            const res = await API.get("/keywords")
            setKeywords(res.data)
        } catch (e) {
            toast.error("Failed to fetch keywords")
        }
    }

    const uploadKeywords = async (file) => {
        try {
            const formData = new FormData()
            formData.append("file", file)
            const res = await API.post("/keywords/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" }
            })
            fetchKeywords()
            return { success: true, message: res.data.message }
        } catch (e) {
            console.error("Upload failed", e)
            return { success: false, message: e.response?.data?.detail || e.message }
        }
    }

    // New Config Methods
    const getConfig = async () => {
        try {
            const res = await API.get("/config")
            return res.data
        } catch (e) {
            toast.error("Failed to fetch config")
            return {}
        }
    }

    const updateConfig = async (settings) => {
        try {
            await API.post("/config", settings)
            toast.success("Configuration updated")
        } catch (e) {
            toast.error("Failed to update configuration")
        }
    }

    return {
        status,
        metrics,
        logs,
        keywords,
        control,
        fetchKeywords,
        uploadKeywords,
        getConfig,
        updateConfig
    }
}
