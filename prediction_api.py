import { Routes, Route, Link } from 'react-router-dom'
import Home from './pages/Home'
import Predict from './pages/Predict'
import Models from './pages/Models'
import Calculator from './pages/Calculator'
import LiveGames from './pages/LiveGames'
import Splits from './pages/Splits'
import Esoteric from './pages/Esoteric'
import PlayerProps from './pages/PlayerProps'

function App() {
  return (
    <div className="app">
      <nav className="navbar">
        <Link to="/" className="navbar-brand">
          Bookie<span>-o-em</span>
        </Link>
        <ul className="nav-links">
          <li><Link to="/">Home</Link></li>
          <li><Link to="/live">Odds</Link></li>
          <li><Link to="/props">Props</Link></li>
          <li><Link to="/splits">Splits</Link></li>
          <li><Link to="/esoteric">🔮</Link></li>
          <li><Link to="/calculator">Calc</Link></li>
        </ul>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/live" element={<LiveGames />} />
        <Route path="/props" element={<PlayerProps />} />
        <Route path="/splits" element={<Splits />} />
        <Route path="/esoteric" element={<Esoteric />} />
        <Route path="/predict" element={<Predict />} />
        <Route path="/models" element={<Models />} />
        <Route path="/calculator" element={<Calculator />} />
      </Routes>
    </div>
  )
}

export default App
