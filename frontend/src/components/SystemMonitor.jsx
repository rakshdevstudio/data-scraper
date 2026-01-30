import React from "react";
import { Cpu, Database, Server } from "lucide-react";

export default function SystemMonitor({ metrics }) {
    if (!metrics || !metrics.system) return null;

    const { cpu_percent, memory_percent, active_threads, uptime } = metrics.system;

    return (
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 dark:bg-gray-800 dark:border-gray-700">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Server size={20} /> System Monitor
            </h3>

            <div className="space-y-4">
                {/* CPU */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-500 font-medium flex items-center gap-2"><Cpu size={14} /> CPU Usage</span>
                        <span className="font-bold">{cpu_percent}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
                        <div
                            className={`h-2.5 rounded-full ${cpu_percent > 80 ? 'bg-red-600' : 'bg-blue-600'}`}
                            style={{ width: `${Math.min(cpu_percent, 100)}%` }}
                        ></div>
                    </div>
                </div>

                {/* Memory */}
                <div>
                    <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-500 font-medium flex items-center gap-2"><Database size={14} /> Memory Usage</span>
                        <span className="font-bold">{memory_percent}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700">
                        <div
                            className={`h-2.5 rounded-full ${memory_percent > 80 ? 'bg-red-600' : 'bg-purple-600'}`}
                            style={{ width: `${Math.min(memory_percent, 100)}%` }}
                        ></div>
                    </div>
                </div>

                {/* Threads */}
                <div className="flex justify-between items-center text-sm pt-2 border-t border-gray-100 dark:border-gray-700">
                    <span className="text-gray-500">Active Threads</span>
                    <span className="font-mono bg-gray-100 px-2 py-1 rounded text-xs">{active_threads}</span>
                </div>

                {/* Uptime */}
                <div className="flex justify-between items-center text-sm">
                    <span className="text-gray-500">Node Uptime</span>
                    <span className="font-mono text-xs text-gray-700 dark:text-gray-300">{uptime}s</span>
                </div>
            </div>
        </div>
    );
}
