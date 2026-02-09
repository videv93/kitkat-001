import { useAuth } from '../hooks/useAuth'

export default function DashboardPage() {
  const { logout } = useAuth()

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <header className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold">kitkat-001</h1>
        <nav className="flex gap-4">
          <a href="#settings" className="text-gray-400 hover:text-white">
            Settings
          </a>
          <button
            onClick={logout}
            className="text-gray-400 hover:text-white"
          >
            Disconnect
          </button>
        </nav>
      </header>
      <main className="p-6">
        <p className="text-gray-400">Dashboard — coming in Story 7.1</p>
      </main>
    </div>
  )
}
