import { Play, Pause, Square, Terminal } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useScraper } from "@/hooks/useScraper"
import { motion } from "framer-motion"

export function Dashboard() {
    const { status, metrics, logs, control, resetFailed, resetAll } = useScraper()

    const getStatusColor = (s) => {
        switch (s) {
            case "running": return "success";
            case "paused": return "warning";
            case "stopped": return "destructive";
            default: return "default";
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight text-white">Overview</h1>
                <div className="flex items-center gap-2">
                    <Badge variant={getStatusColor(status)} className="uppercase tracking-widest">
                        {status}
                    </Badge>
                </div>
            </div>

            {/* Metrics Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <MetricCard title="Total Keywords" value={metrics.total} delay={0} />
                <MetricCard title="Completed" value={metrics.done} delay={0.1} />
                <MetricCard title="Pending" value={metrics.pending} delay={0.2} />
                <MetricCard title="Failed" value={metrics.failed} delay={0.3} color="text-red-400" />
            </div>

            {/* Reset Controls - Show when there are failed keywords */}
            {metrics.failed > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex gap-3 items-center justify-center p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg"
                >
                    <span className="text-yellow-400 text-sm">
                        ⚠️ {metrics.failed.toLocaleString()} failed keywords detected
                    </span>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                            if (confirm(`Reset ${metrics.failed.toLocaleString()} failed keywords to pending? They will be retried.`)) {
                                resetFailed()
                            }
                        }}
                        className="border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/10"
                    >
                        Retry Failed
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                            if (confirm(`Reset ALL non-completed keywords to pending? This will retry ${metrics.failed + metrics.processing} keywords.`)) {
                                resetAll()
                            }
                        }}
                        className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                    >
                        Reset All
                    </Button>
                </motion.div>
            )}

            {/* Control & Logs */}
            <div className="grid gap-4 md:grid-cols-7">

                {/* Control Panel */}
                <Card className="md:col-span-3 border-white/10 bg-white/5">
                    <CardHeader>
                        <CardTitle>Control Panel</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-3">
                            <Button
                                variant="neon"
                                onClick={() => control("start")}
                                disabled={status === "running"}
                                className="h-24 flex flex-col gap-2"
                            >
                                <Play className="h-6 w-6" />
                                START
                            </Button>
                            <Button
                                variant="destructive"
                                onClick={() => control("stop")}
                                disabled={status === "idle"}
                                className="h-24 flex flex-col gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20"
                            >
                                <Square className="h-6 w-6" />
                                STOP
                            </Button>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            {status === "paused" ? (
                                <Button onClick={() => control("resume")} className="col-span-2">Resume</Button>
                            ) : (
                                <Button
                                    variant="secondary"
                                    onClick={() => control("pause")}
                                    disabled={status !== "running"}
                                    className="col-span-2"
                                >
                                    <Pause className="mr-2 h-4 w-4" /> Pause
                                </Button>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Logs */}
                <Card className="md:col-span-4 border-white/10 bg-black/40">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Live Logs</CardTitle>
                        <Terminal className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="h-[300px] overflow-y-auto font-mono text-xs space-y-1 p-2 rounded-md bg-black/50 text-green-400/80">
                            {logs.map((log) => (
                                <div key={log.id} className="border-b border-white/5 pb-1 last:border-0">
                                    <span className="text-white/30 mr-2">
                                        {new Date(log.timestamp).toLocaleTimeString()}
                                    </span>
                                    <span className={log.level === "ERROR" ? "text-red-400 font-bold" : ""}>
                                        {log.message}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}

function MetricCard({ title, value, delay, color = "text-white" }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay }}
        >
            <Card className="border-white/10 bg-white/5 backdrop-blur-lg">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                        {title}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className={`text-2xl font-bold ${color}`}>{value}</div>
                </CardContent>
            </Card>
        </motion.div>
    )
}
