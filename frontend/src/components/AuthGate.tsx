import { useAuth } from '../hooks/useAuth'
import ConnectPage from '../pages/ConnectPage'
import DashboardPage from '../pages/DashboardPage'

export default function AuthGate() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <ConnectPage />
  }

  return <DashboardPage />
}
