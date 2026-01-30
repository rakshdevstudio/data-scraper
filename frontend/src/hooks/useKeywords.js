import { useState, useCallback } from "react";
import { getKeywords, uploadKeywords as apiUpload, resetFailedKeywords, resetSkippedKeywords, resetAllKeywords } from "../services/api";
import { toast } from "sonner";

export function useKeywords() {
    const [keywords, setKeywords] = useState([]);
    const [loading, setLoading] = useState(false);
    const [pagination, setPagination] = useState({ page: 1, limit: 100, total: 0, total_pages: 1 });

    const fetchKeywords = useCallback(async (page = 1, limit = 100, status = null) => {
        setLoading(true);
        try {
            const data = await getKeywords(page, limit, status);
            setKeywords(data.items || []);
            setPagination({
                page: data.page,
                limit: data.limit,
                total: data.total,
                total_pages: data.total_pages
            });
        } catch (error) {
            toast.error("Failed to fetch keywords");
        } finally {
            setLoading(false);
        }
    }, []);

    const uploadFile = async (file, mode) => {
        try {
            const res = await apiUpload(file, mode);
            toast.success(res.message);
            fetchKeywords(1, pagination.limit); // Reset to page 1
            return true;
        } catch (error) {
            toast.error(error.response?.data?.detail || "Upload failed");
            return false;
        }
    };

    const resetFailed = async () => {
        try {
            const res = await resetFailedKeywords();
            toast.success(res.message);
            fetchKeywords(pagination.page, pagination.limit);
        } catch (error) {
            toast.error("Failed to reset failed keywords");
        }
    };

    const resetSkipped = async () => {
        try {
            const res = await resetSkippedKeywords();
            toast.success(res.message);
            fetchKeywords(pagination.page, pagination.limit);
        } catch (error) {
            toast.error("Failed to reset skipped keywords");
        }
    };

    const resetAll = async () => {
        try {
            const res = await resetAllKeywords();
            toast.success(res.message);
            fetchKeywords(pagination.page, pagination.limit);
        } catch (error) {
            toast.error("Failed to reset all keywords");
        }
    };

    return {
        keywords,
        loading,
        pagination,
        fetchKeywords,
        uploadFile,
        resetFailed,
        resetSkipped,
        resetAll
    };
}
