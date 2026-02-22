import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import ConnectPage from '../pages/ConnectPage'
import DashboardPage from '../pages/DashboardPage'
import SettingsPage from '../pages/SettingsPage'

type View = 'dashboard' | 'settings'

function getViewFromHash(): View {
  const hash = window.location.hash.replace('#', '')
  return hash === 'settings' ? 'settings' : 'dashboard'
}

export default function AuthGate() {
  const { isAuthenticated } = useAuth()
  const [currentView, setCurrentView] = useState<View>(getViewFromHash)

  const onNavigate = useCallback((view: View) => {
    window.location.hash = view === 'dashboard' ? '' : view
    setCurrentView(view)
  }, [])

  useEffect(() => {
    const handleHashChange = () => setCurrentView(getViewFromHash())
    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  if (!isAuthenticated) {
    return <ConnectPage />
  }

  if (currentView === 'settings') {
    return <SettingsPage onNavigate={onNavigate} />
  }

  return <DashboardPage onNavigate={onNavigate} />
}
