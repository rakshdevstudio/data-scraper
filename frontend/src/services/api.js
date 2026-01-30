import axios from "axios";
import { toast } from "sonner";

const API = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
    timeout: 60000,
});

// Interceptor for errors
API.interceptors.response.use(
    (response) => response,
    (error) => {
        const msg = error.response?.data?.detail || error.message || "An unexpected error occurred";
        console.error("API Error:", msg);
        // We can show toast here globally for critical errors
        // But usually better to let call site handle or just show error toast for 500s
        if (error.response?.status >= 500) {
            toast.error(`Server Error: ${msg}`);
        }
        return Promise.reject(error);
    }
);

// API Methods

// Scraper Status & Control
export const getScraperStatus = async () => {
    const response = await API.get("/status");
    return response.data;
};

export const getMetrics = async () => {
    const response = await API.get("/metrics");
    return response.data;
};

export const getLogs = async (limit = 50) => {
    const response = await API.get(`/logs?limit=${limit}`);
    return response.data;
};

export const controlScraper = async (action) => {
    // action: start, stop, pause, resume
    const response = await API.post(`/control/${action}`);
    return response.data;
};

// Keyword Management
export const getKeywords = async (page = 1, limit = 100, status = null) => {
    const params = { page, limit };
    if (status) params.status = status;
    const response = await API.get("/keywords", { params });
    return response.data;
};

export const uploadKeywords = async (file, mode = "add") => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mode", mode);
    const response = await API.post("/keywords/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" }
    });
    return response.data;
};

export const resetFailedKeywords = async () => {
    const response = await API.post("/keywords/reset-failed");
    return response.data;
};

export const resetSkippedKeywords = async () => {
    const response = await API.post("/keywords/reset-skipped");
    return response.data;
};

export const resetAllKeywords = async () => {
    const response = await API.post("/keywords/reset-all");
    return response.data;
};

// Configuration
export const getConfig = async () => {
    const response = await API.get("/config");
    return response.data;
};

export const updateConfig = async (settings) => {
    const response = await API.post("/config", settings);
    return response.data;
};

export const getStats = async () => {
    try {
        const response = await API.get("/results/stats");
        return response.data;
    } catch (error) {
        return null;
    }
};

export default API;
