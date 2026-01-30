import { useState } from 'react'
import { Sidebar } from '@/components/Sidebar'
import Dashboard from '@/pages/Dashboard'
import Keywords from '@/pages/Keywords'

import { Toaster } from 'sonner'

function App() {
  const [activeTab, setActiveTab] = useState("dashboard")

  return (
    <div className="flex h-screen bg-[#0B0F1A] text-white">
      <Toaster position="top-right" theme="dark" />
      {/* Background Gradient Ambience */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] rounded-full bg-indigo-500/10 blur-[120px]" />
        <div className="absolute top-[40%] right-[0%] w-[40%] h-[40%] rounded-full bg-purple-500/10 blur-[120px]" />
      </div>

      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <main className="flex-1 overflow-y-auto p-8 relative z-10">
        <div className="max-w-7xl mx-auto">
          {activeTab === "dashboard" && <Dashboard />}
          {activeTab === "keywords" && <Keywords />}
          {activeTab === "settings" && (
            <div className="flex items-center justify-center h-[50vh] text-muted-foreground">
              Settings module coming soon...
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
