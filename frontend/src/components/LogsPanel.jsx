import React, { useEffect, useRef } from "react";
import { ScrollText } from "lucide-react";

export default function LogsPanel({ logs }) {
    const scrollRef = useRef(null);

    // Auto-scroll to bottom when logs update
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    const getLogColor = (level) => {
        switch (level) {
            case "ERROR": return "text-red-600 bg-red-50";
            case "WARNING": return "text-amber-600 bg-amber-50";
            case "CRITICAL": return "text-red-700 bg-red-100 font-bold";
            case "INFO": return "text-blue-600";
            default: return "text-gray-600";
        }
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 dark:bg-gray-800 dark:border-gray-700 flex flex-col h-96">
            <div className="p-4 border-b border-gray-100 dark:border-gray-700 flex justify-between items-center">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <ScrollText size={20} /> Live Logs
                </h3>
                <span className="text-xs text-gray-400">Auto-scrolling</span>
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 font-mono text-sm space-y-1 bg-gray-50 dark:bg-gray-900"
            >
                {logs && logs.length > 0 ? (
                    logs.map((log, index) => (
                        <div key={index} className="flex gap-2 hover:bg-gray-100 dark:hover:bg-gray-800 p-0.5 rounded">
                            <span className="text-gray-400 text-xs whitespace-nowrap select-none">
                                [{new Date(log.timestamp).toLocaleTimeString()}]
                            </span>
                            <span className={`px-1.5 py-0.5 rounded text-xs font-bold leading-none flex items-center ${getLogColor(log.level)}`}>
                                {log.level}
                            </span>
                            <span className="text-gray-700 dark:text-gray-300 break-all">
                                {log.message}
                            </span>
                        </div>
                    ))
                ) : (
                    <div className="text-gray-400 text-center italic mt-10">No logs available...</div>
                )}
            </div>
        </div>
    );
}
