import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import MembersPage from './pages/MembersPage'
import DropoutPage from './pages/DropoutPage'
import RevenuePage from './pages/RevenuePage'
import ChatPage from './pages/ChatPage'
import Sidebar from './components/Sidebar'

const queryClient = new QueryClient()

function PrivateRoute({ children }) {
  const token = localStorage.getItem('staff_token')
  if (!token) return <Navigate to="/login" replace />
  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <Sidebar />
      <main style={{ flex: 1, overflowY: 'auto', marginLeft: '240px', background: '#f3f4f6', minHeight: '100%' }}>
        {children}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/overview" element={<PrivateRoute><OverviewPage /></PrivateRoute>} />
          <Route path="/members" element={<PrivateRoute><MembersPage /></PrivateRoute>} />
          <Route path="/dropout" element={<PrivateRoute><DropoutPage /></PrivateRoute>} />
          <Route path="/revenue" element={<PrivateRoute><RevenuePage /></PrivateRoute>} />
          <Route path="/chat" element={<PrivateRoute><ChatPage /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
