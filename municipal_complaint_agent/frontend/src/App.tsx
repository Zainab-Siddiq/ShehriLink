import { Route, Routes } from 'react-router-dom'
import { AdminLayout, PublicLayout } from './components/Layouts'
import ComplaintDetail from './pages/admin/ComplaintDetail'
import Complaints from './pages/admin/Complaints'
import Dashboard from './pages/admin/Dashboard'
import Escalations from './pages/admin/Escalations'
import Teams from './pages/admin/Teams'
import Landing from './pages/Landing'
import NotFound from './pages/NotFound'
import Submit from './pages/Submit'
import Track from './pages/Track'

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="submit" element={<Submit />} />
        <Route path="track" element={<Track />} />
        <Route path="track/:id" element={<Track />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="admin" element={<AdminLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="complaints" element={<Complaints />} />
        <Route path="complaints/:id" element={<ComplaintDetail />} />
        <Route path="escalations" element={<Escalations />} />
        <Route path="teams" element={<Teams />} />
      </Route>
    </Routes>
  )
}
