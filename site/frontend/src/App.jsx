import { Routes, Route } from 'react-router-dom'
import Layout from './Layout'
import Home from './Home'
import Lab from './Lab'
import PySimplePage from './PySimplePage'
import C2Dashboard from './C2Dashboard'
import './App.css'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}> 
        <Route index element={<C2Dashboard />} />
        <Route path="lab" element={<Lab />} />
        <Route path="py_simple" element={<PySimplePage />} />
      </Route>
    </Routes>
  )
}
