import axios from "axios";
import { toast } from "sonner";

const API = axios.create({
    baseURL: "http://localhost:8000",
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

export default API;
