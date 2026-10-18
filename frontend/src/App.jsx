import { Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import CropDoctor from './pages/CropDoctor'
import Dashboard from './pages/Dashboard'
import DiseaseHistory from './pages/DiseaseHistory'
import Farms from './pages/Farms'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Profile from './pages/Profile'
import Register from './pages/Register'
import ProtectedRoute from './routes/ProtectedRoute'

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/farms" element={<ProtectedRoute><Farms /></ProtectedRoute>} />
        <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
        <Route path="/crop-doctor" element={<ProtectedRoute><CropDoctor /></ProtectedRoute>} />
        <Route path="/crop-doctor/history" element={<ProtectedRoute><DiseaseHistory /></ProtectedRoute>} />
      </Routes>
    </>
  )
}