import React from "react";
import { controlScraper } from "../services/api";
import { toast } from "sonner";
import { Play, Pause, Square, RefreshCw } from "lucide-react";

export default function ControlPanel({ status, isLoading }) {
    const handleControl = async (action) => {
        try {
            await controlScraper(action);
            toast.success(`Sent command: ${action}`);
        } catch (error) {
            toast.error(`Failed to ${action} scraper`);
        }
    };

    const isRunning = status === "running";
    const isPaused = status === "paused";
    const isIdle = status === "idle" || status === "stopped" || status === "error";

    if (isLoading) return <div className="animate-pulse h-16 bg-gray-100 rounded-lg"></div>;

    return (
        <div className="flex flex-wrap gap-4 items-center p-4 bg-white rounded-lg shadow-sm border border-gray-100 dark:bg-gray-800 dark:border-gray-700">
            <h3 className="text-lg font-semibold min-w-32">Controls</h3>

            {/* Start Button */}
            <button
                onClick={() => handleControl("start")}
                disabled={!isIdle}
                className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${isIdle
                    ? "bg-green-600 text-white hover:bg-green-700"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed dark:bg-gray-700"
                    }`}
            >
                <Play size={18} /> Start
            </button>

            {/* Pause/Resume Button */}
            {isPaused ? (
                <button
                    onClick={() => handleControl("resume")}
                    className="flex items-center gap-2 px-4 py-2 rounded-md font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                >
                    <Play size={18} /> Resume
                </button>
            ) : (
                <button
                    onClick={() => handleControl("pause")}
                    disabled={!isRunning}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${isRunning
                        ? "bg-amber-500 text-white hover:bg-amber-600"
                        : "bg-gray-200 text-gray-400 cursor-not-allowed dark:bg-gray-700"
                        }`}
                >
                    <Pause size={18} /> Pause
                </button>
            )}

            {/* Stop Button */}
            <button
                onClick={() => handleControl("stop")}
                disabled={isIdle}
                className={`flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${!isIdle
                    ? "bg-red-600 text-white hover:bg-red-700"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed dark:bg-gray-700"
                    }`}
            >
                <Square size={18} /> Stop
            </button>

            <div className="ml-auto flex items-center gap-2 text-sm text-gray-500">
                Status:
                <span className={`px-2 py-1 rounded-full text-xs font-bold uppercase ${status === "running" ? "bg-green-100 text-green-800" :
                    status === "paused" ? "bg-amber-100 text-amber-800" :
                        status === "error" ? "bg-red-100 text-red-800" :
                            "bg-gray-100 text-gray-800"
                    }`}>
                    {status}
                </span>
            </div>
        </div>
    );
}
