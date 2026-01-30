import { Upload, Download, Search } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useScraper } from "@/hooks/useScraper"
import { useEffect, useState } from "react"
import { motion } from "framer-motion"

export default function Keywords() {
    const { keywords, fetchKeywords, uploadKeywords } = useScraper()
    const [filter, setFilter] = useState("")
    const [uploadMode, setUploadMode] = useState("add")

    useEffect(() => {
        fetchKeywords()
    }, [])

    const handleFileUpload = async (e) => {
        if (e.target.files?.[0]) {
            // Confirm if using replace mode
            if (uploadMode === "replace") {
                const confirmed = confirm(
                    "⚠️ REPLACE MODE: This will DELETE ALL existing keywords and replace with the new file. Continue?"
                )
                if (!confirmed) {
                    e.target.value = ""
                    return
                }
            }

            const res = await uploadKeywords(e.target.files[0], uploadMode)
            if (res.success) {
                alert(`✅ ${res.message}`)
                // Refresh keywords list to show new data
                await fetchKeywords()
            } else {
                alert(`❌ Upload failed: ${res.message}`)
            }
            e.target.value = "" // Reset input
        }
    }

    const filtered = keywords.filter(k => k.text.toLowerCase().includes(filter.toLowerCase()))

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight text-white">Keywords Manager</h1>
                <div className="flex gap-2 items-center">
                    {/* Upload Mode Selector */}
                    <select
                        value={uploadMode}
                        onChange={(e) => setUploadMode(e.target.value)}
                        className="bg-black/20 border border-white/10 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                        <option value="add">➕ Add New Only</option>
                        <option value="sync">🔄 Sync (Add + Reset)</option>
                        <option value="replace">🗑️ Clear & Replace All</option>
                    </select>

                    <Button variant="outline" className="gap-2 relative overflow-hidden">
                        <input
                            type="file"
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            onChange={handleFileUpload}
                            accept=".xlsx,.xls"
                        />
                        <Upload className="h-4 w-4" />
                        Import Excel
                    </Button>
                    <Button variant="outline" className="gap-2">
                        <Download className="h-4 w-4" />
                        Export Results
                    </Button>
                </div>
            </div>

            <Card className="border-white/10 bg-white/5 backdrop-blur-lg">
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <CardTitle>Keywords List</CardTitle>
                        <div className="relative w-64">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <input
                                placeholder="Search keywords..."
                                className="w-full bg-black/20 border border-white/10 rounded-md py-2 pl-8 pr-4 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                onChange={(e) => setFilter(e.target.value)}
                            />
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="rounded-md border border-white/10 overflow-hidden">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-white/5 text-muted-foreground">
                                <tr>
                                    <th className="p-4 font-medium">Keyword</th>
                                    <th className="p-4 font-medium">Status</th>
                                    <th className="p-4 font-medium">Updated</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {filtered.map((k, i) => (
                                    <motion.tr
                                        key={k.id}
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: i * 0.05 }}
                                        className="hover:bg-white/5 transition-colors"
                                    >
                                        <td className="p-4">{k.text}</td>
                                        <td className="p-4">
                                            <Badge variant={getStatusVariant(k.status)}>
                                                {k.status}
                                            </Badge>
                                        </td>
                                        <td className="p-4 text-muted-foreground">
                                            {new Date(k.updated_at).toLocaleDateString()}
                                        </td>
                                    </motion.tr>
                                ))}
                                {filtered.length === 0 && (
                                    <tr>
                                        <td colSpan={3} className="p-8 text-center text-muted-foreground">
                                            No keywords found
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

function getStatusVariant(status) {
    switch (status) {
        case "done": return "success";
        case "processing": return "default"; // blue
        case "failed": return "destructive";
        default: return "secondary"; // gray
    }
}
