import { LayoutDashboard, Database, Settings, Activity } from "lucide-react"

export function Sidebar({ activeTab, setActiveTab }) {
    const menu = [
        { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
        { id: "keywords", icon: Database, label: "Keywords" },
        { id: "settings", icon: Settings, label: "Settings" },
    ]

    return (
        <div className="w-64 border-r bg-card/50 backdrop-blur-xl h-screen flex flex-col p-4 border-white/10">
            <div className="flex items-center gap-2 px-2 mb-8">
                <Activity className="h-6 w-6 text-indigo-400" />
                <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
                    MapsScraper
                </span>
            </div>

            <div className="space-y-1">
                {menu.map((item) => (
                    <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${activeTab === item.id
                                ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                                : "text-muted-foreground hover:bg-white/5 hover:text-white"
                            }`}
                    >
                        <item.icon className="h-4 w-4" />
                        {item.label}
                    </button>
                ))}
            </div>

            <div className="mt-auto">
                <div className="p-4 rounded-lg bg-gradient-to-br from-indigo-900/50 to-purple-900/50 border border-white/5">
                    <p className="text-xs text-indigo-200">System Status</p>
                    <div className="flex items-center gap-2 mt-2">
                        <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-xs font-mono text-white/50">Online</span>
                    </div>
                </div>
            </div>
        </div>
    )
}
