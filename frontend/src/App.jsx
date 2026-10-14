import { Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import Landing from './pages/Landing'

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Landing />} />
      </Routes>
    </>
  )
}