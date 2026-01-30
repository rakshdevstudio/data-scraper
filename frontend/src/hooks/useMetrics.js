import { useState, useEffect } from "react";
import { getMetrics } from "../services/api";

export function useMetrics(intervalMs = 2000) {
    const [metrics, setMetrics] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        let isMounted = true;

        const fetchMetrics = async () => {
            try {
                const data = await getMetrics();
                if (isMounted) {
                    setMetrics(data);
                    setError(null);
                }
            } catch (err) {
                if (isMounted) setError(err);
            }
        };

        fetchMetrics();
        const intervalId = setInterval(fetchMetrics, intervalMs);

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };
    }, [intervalMs]);

    return { metrics, error };
}
