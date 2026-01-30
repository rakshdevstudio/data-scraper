import { useState, useEffect } from "react";
import { getLogs } from "../services/api";

export function useLogs(intervalMs = 2000, limit = 100) {
    const [logs, setLogs] = useState([]);
    const [error, setError] = useState(null);

    useEffect(() => {
        let isMounted = true;

        const fetchLogs = async () => {
            try {
                const data = await getLogs(limit);
                if (isMounted) {
                    setLogs(data);
                    setError(null);
                }
            } catch (err) {
                if (isMounted) setError(err);
            }
        };

        fetchLogs();
        const intervalId = setInterval(fetchLogs, intervalMs);

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };
    }, [intervalMs, limit]);

    return { logs, error };
}
