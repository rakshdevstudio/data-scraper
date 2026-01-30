import React from "react";
import { useScraperStatus } from "../hooks/useScraperStatus";
import { useMetrics } from "../hooks/useMetrics";
import { useLogs } from "../hooks/useLogs";
import ControlPanel from "../components/ControlPanel";
import DashboardStats from "../components/DashboardStats";
import SystemMonitor from "../components/SystemMonitor";
import LogsPanel from "../components/LogsPanel";
import KeywordManager from "../components/KeywordManager";
import { LayoutDashboard } from "lucide-react";

export default function Dashboard() {
    // Use custom hooks for real-time data
    const { status, isLoading: statusLoading } = useScraperStatus(2000);
    const { metrics } = useMetrics(2000);
    const { logs } = useLogs(2000);

    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto pb-20">
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
                <h1 className="text-2xl font-bold flex items-center gap-3">
                    <LayoutDashboard className="text-blue-600" />
                    Scraper Dashboard
                </h1>
                <div className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full dark:bg-gray-800 dark:text-gray-400">
                    v2.5.0 • Production Ready
                </div>
            </div>

            {/* Stats Cards */}
            <DashboardStats metrics={metrics} />

            {/* Main Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Left Col: Controls & System */}
                <div className="space-y-6 lg:col-span-2">

                    {/* Control Panel */}
                    <ControlPanel status={status} isLoading={statusLoading} />

                    {/* Keyword Manager (Table) */}
                    <div className="h-96">
                        <KeywordManager />
                    </div>

                    {/* Logs */}
                    <LogsPanel logs={logs} />
                </div>

                {/* Right Col: System Monitor & Status */}
                <div className="space-y-6">
                    <SystemMonitor metrics={metrics} />

                    {/* Info Card / Quick Status */}
                    <div className="bg-gradient-to-br from-blue-600 to-indigo-700 rounded-lg p-6 text-white shadow-lg">
                        <h3 className="font-bold text-lg mb-2">System Status</h3>
                        <p className="opacity-90 mb-4 text-sm">
                            The new Scraper Engine is running in embedded mode with auto-healing capabilities.
                        </p>
                        <div className="flex items-center gap-3 text-sm font-medium bg-white/10 p-3 rounded-lg backdrop-blur-sm">
                            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                            Backend Online
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
