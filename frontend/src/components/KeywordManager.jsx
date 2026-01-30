import React, { useEffect } from "react";
import { useKeywords } from "../hooks/useKeywords";
import { Upload, Trash2, RefreshCw, FileText, CheckCircle, AlertOctagon, Clock, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function KeywordManager() {
    const {
        keywords,
        loading,
        pagination,
        fetchKeywords,
        uploadFile,
        resetFailed,
        resetSkipped,
        resetAll
    } = useKeywords();

    useEffect(() => {
        fetchKeywords(1, 10); // Initial fetch, smaller limit for widget view
    }, [fetchKeywords]);

    const handleFileUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        await uploadFile(file, "add");
    };

    const getStatusBadge = (status) => {
        switch (status) {
            case "DONE": return <span className="px-2 py-0.5 rounded text-xs font-bold bg-green-100 text-green-800 flex items-center gap-1"><CheckCircle size={10} /> Done</span>;
            case "FAILED": return <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-100 text-red-800 flex items-center gap-1"><AlertOctagon size={10} /> Failed</span>;
            case "PROCESSING": return <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-100 text-blue-800 flex items-center gap-1"><RefreshCw size={10} className="animate-spin" /> Processing</span>;
            case "SKIPPED": return <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-100 text-amber-800 flex items-center gap-1"><AlertTriangle size={10} /> Skipped</span>;
            default: return <span className="px-2 py-0.5 rounded text-xs font-bold bg-gray-100 text-gray-600 flex items-center gap-1"><Clock size={10} /> Pending</span>;
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 dark:bg-gray-800 dark:border-gray-700 flex flex-col h-full">
            <div className="p-4 border-b border-gray-100 dark:border-gray-700 flex flex-wrap justify-between items-center gap-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <FileText size={20} /> Keyword Manager
                </h3>

                <div className="flex gap-2">
                    <label className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 text-white rounded text-sm font-medium hover:bg-indigo-700 cursor-pointer transition-colors">
                        <Upload size={14} /> Upload CSV
                        <input type="file" className="hidden" accept=".csv,.xlsx" onChange={handleFileUpload} />
                    </label>
                </div>
            </div>

            <div className="p-4 bg-gray-50 dark:bg-gray-900 border-b border-gray-100 dark:border-gray-700 flex gap-2 overflow-x-auto">
                <button onClick={resetFailed} className="px-3 py-1 bg-white border border-red-200 text-red-600 rounded text-xs font-medium hover:bg-red-50 flex items-center gap-1">
                    <RefreshCw size={12} /> Reset Failed
                </button>
                <button onClick={resetSkipped} className="px-3 py-1 bg-white border border-amber-200 text-amber-600 rounded text-xs font-medium hover:bg-amber-50 flex items-center gap-1">
                    <RefreshCw size={12} /> Reset Skipped
                </button>
                <button onClick={() => { if (window.confirm('Reset ALL keywords?')) resetAll() }} className="px-3 py-1 bg-white border border-gray-200 text-gray-600 rounded text-xs font-medium hover:bg-gray-50 flex items-center gap-1 ml-auto">
                    <Trash2 size={12} /> Reset All
                </button>
            </div>

            <div className="flex-1 overflow-auto p-0">
                <table className="w-full text-sm text-left">
                    <thead className="bg-gray-50 dark:bg-gray-700 text-xs uppercase text-gray-500 font-medium sticky top-0">
                        <tr>
                            <th className="px-4 py-3">Keyword</th>
                            <th className="px-4 py-3">City</th>
                            <th className="px-4 py-3">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {keywords?.length > 0 ? (
                            keywords.map((k) => (
                                <tr key={k.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                                    <td className="px-4 py-2 font-medium">{k.text}</td>
                                    <td className="px-4 py-2 text-gray-500">{k.city || "-"}</td>
                                    <td className="px-4 py-2">{getStatusBadge(k.status)}</td>
                                </tr>
                            ))
                        ) : (
                            <tr>
                                <td colSpan="3" className="px-4 py-8 text-center text-gray-400">
                                    {loading ? "Loading..." : "No keywords found"}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="p-2 border-t border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-xs text-center text-gray-500">
                Showing top 10 recent keywords. Visit Keywords page for full list.
            </div>
        </div>
    );
}
