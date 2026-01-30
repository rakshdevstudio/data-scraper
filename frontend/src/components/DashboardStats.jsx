import React from "react";
import { Activity, CheckCircle, Clock, AlertTriangle, AlertOctagon } from "lucide-react";

const StatCard = ({ title, value, icon: Icon, color }) => (
    <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-100 dark:bg-gray-800 dark:border-gray-700 flex items-center gap-4">
        <div className={`p-3 rounded-full ${color.bg} ${color.text}`}>
            <Icon size={24} />
        </div>
        <div>
            <p className="text-sm text-gray-500 font-medium">{title}</p>
            <h4 className="text-2xl font-bold dark:text-white">{value}</h4>
        </div>
    </div>
);

export default function DashboardStats({ metrics }) {
    if (!metrics) return null;

    const stats = [
        {
            title: "Total Keywords",
            value: metrics.total || 0,
            icon: Activity,
            color: { bg: "bg-blue-100", text: "text-blue-600" }
        },
        {
            title: "Completed",
            value: metrics.done || 0,
            icon: CheckCircle,
            color: { bg: "bg-green-100", text: "text-green-600" }
        },
        {
            title: "Pending",
            value: metrics.pending || 0,
            icon: Clock,
            color: { bg: "bg-indigo-100", text: "text-indigo-600" }
        },
        {
            title: "Failed",
            value: metrics.failed || 0,
            icon: AlertOctagon,
            color: { bg: "bg-red-100", text: "text-red-600" }
        },
        {
            title: "Skipped",
            value: metrics.skipped || 0,
            icon: AlertTriangle,
            color: { bg: "bg-amber-100", text: "text-amber-600" }
        }
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {stats.map((stat) => (
                <StatCard key={stat.title} {...stat} />
            ))}
        </div>
    );
}
