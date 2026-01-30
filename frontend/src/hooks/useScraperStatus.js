import { useState, useEffect } from "react";
import { getScraperStatus } from "../services/api";

export function useScraperStatus(intervalMs = 2000) {
    const [status, setStatus] = useState("idle");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        let isMounted = true;

        const fetchStatus = async () => {
            try {
                const data = await getScraperStatus();
                if (isMounted) {
                    setStatus(data.status);
                    setError(null);
                }
            } catch (err) {
                if (isMounted) {
                    setError(err);
                }
            } finally {
                if (isMounted) setIsLoading(false);
            }
        };

        // Initial fetch
        fetchStatus();

        // Polling
        const intervalId = setInterval(fetchStatus, intervalMs);

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };
    }, [intervalMs]);

    return { status, isLoading, error };
}
