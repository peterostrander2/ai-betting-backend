# Esoteric Signals Frontend Handoff

**Date:** 2026-01-15
**Backend Version:** v14.8
**API Base:** https://web-production-7b2a.up.railway.app
**Focus:** Building out the Esoteric Engine UI

---

## Overview

The Esoteric Engine provides 10+ signals across 4 categories:
- **JARVIS/Symbolic:** Founder's Echo, Life Path Sync, Biorhythms
- **Arcane Physics:** Gann's Square, 50% Retracement, Schumann, Atmospheric
- **Collective/Sentiment:** Noosphere Velocity, Void Moon
- **Parlay:** Teammate Void, Correlation Matrix

---

## Esoteric Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/esoteric/today-energy` | GET | Daily energy score & outlook |
| `/live/esoteric-edge` | GET | Full esoteric analysis |
| `/live/noosphere/status` | GET | Global consciousness indicators |
| `/live/gann-physics-status` | GET | GANN geometric signals |
| `/live/astro-status` | GET | Full astrological analysis |
| `/live/planetary-hour` | GET | Current planetary hour ruler |
| `/live/nakshatra` | GET | Current lunar mansion |
| `/live/retrograde-status` | GET | Mercury/Venus/Mars retrograde |
| `/live/esoteric-analysis` | GET | Complete pick analysis |

---

## 1. Daily Energy Dashboard

### Endpoint: `/esoteric/today-energy`

**Response Schema:**
```json
{
  "date": "2026-01-15",
  "betting_outlook": "FAVORABLE",
  "overall_energy": 7.0,
  "moon_phase": "sagittarius",
  "void_moon_periods": [
    { "start": "14:00 UTC", "end": "18:00 UTC" }
  ],
  "schumann_reading": {
    "frequency_hz": 7.83,
    "status": "NORMAL"
  },
  "planetary_hours": {
    "current_hour": 5,
    "ruler": "Mars",
    "quality": "AGGRESSIVE"
  },
  "noosphere": {
    "velocity": 68.5,
    "trend": "RISING",
    "signal": "MOMENTUM_BUILD"
  },
  "recommendation": "Energy aligned. Trust your analysis today."
}
```

### React Component

```jsx
function DailyEnergyCard() {
  const [energy, setEnergy] = useState(null);

  useEffect(() => {
    fetch('https://web-production-7b2a.up.railway.app/esoteric/today-energy')
      .then(r => r.json())
      .then(setEnergy);
  }, []);

  if (!energy) return <Skeleton />;

  const outlookColors = {
    FAVORABLE: '#22c55e',
    NEUTRAL: '#eab308',
    CAUTIOUS: '#ef4444'
  };

  return (
    <div className="energy-card">
      {/* Header */}
      <div className="energy-header">
        <h2>Daily Energy</h2>
        <span className="date">{energy.date}</span>
      </div>

      {/* Main Score */}
      <div className="energy-score">
        <div
          className="score-circle"
          style={{ borderColor: outlookColors[energy.betting_outlook] }}
        >
          <span className="score">{energy.overall_energy.toFixed(1)}</span>
          <span className="max">/10</span>
        </div>
        <span
          className="outlook"
          style={{ color: outlookColors[energy.betting_outlook] }}
        >
          {energy.betting_outlook}
        </span>
      </div>

      {/* Moon Phase */}
      <div className="moon-section">
        <MoonIcon phase={energy.moon_phase} />
        <span className="moon-sign">{energy.moon_phase}</span>
        {energy.void_moon_periods.length > 0 && (
          <span className="void-warning">
            ⚠️ Void Moon: {energy.void_moon_periods[0].start} - {energy.void_moon_periods[0].end}
          </span>
        )}
      </div>

      {/* Schumann Resonance */}
      <div className="schumann">
        <span className="label">Schumann:</span>
        <span className="value">{energy.schumann_reading.frequency_hz} Hz</span>
        <span className={`status status-${energy.schumann_reading.status.toLowerCase()}`}>
          {energy.schumann_reading.status}
        </span>
      </div>

      {/* Planetary Hour */}
      <div className="planetary">
        <span className="ruler">{energy.planetary_hours.ruler}</span>
        <span className="quality">{energy.planetary_hours.quality}</span>
      </div>

      {/* Recommendation */}
      <div className="recommendation">
        <p>{energy.recommendation}</p>
      </div>
    </div>
  );
}
```

### CSS Styling

```css
.energy-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 16px;
  padding: 24px;
  color: white;
}

.energy-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 24px 0;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 4px solid;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-circle .score {
  font-size: 3rem;
  font-weight: bold;
}

.score-circle .max {
  font-size: 1rem;
  opacity: 0.6;
}

.outlook {
  font-size: 1.25rem;
  font-weight: 600;
  margin-top: 8px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.void-warning {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid #ef4444;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 0.875rem;
  margin-top: 8px;
}

.status-normal { color: #22c55e; }
.status-elevated { color: #eab308; }
.status-spike { color: #ef4444; }
```

---

## 2. Noosphere Status Widget

### Endpoint: `/live/noosphere/status`

**Response Schema:**
```json
{
  "status": "ACTIVE",
  "global_coherence": 0.723,
  "anomaly_detected": true,
  "anomaly_strength": "MODERATE",
  "interpretation": "Collective attention spike - information asymmetry likely",
  "betting_signal": "FADE PUBLIC",
  "modules": {
    "insider_leak": { "status": "monitoring", "signal": "NEUTRAL" },
    "main_character_syndrome": { "status": "active", "signal": "CHECK NARRATIVES" },
    "phantom_injury": { "status": "scanning", "signal": "NO ALERTS" }
  },
  "timestamp": "2026-01-15T14:32:00"
}
```

### React Component

```jsx
function NoosphereWidget() {
  const [noosphere, setNoosphere] = useState(null);

  useEffect(() => {
    const fetchData = () => {
      fetch('https://web-production-7b2a.up.railway.app/live/noosphere/status')
        .then(r => r.json())
        .then(setNoosphere);
    };

    fetchData();
    const interval = setInterval(fetchData, 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  if (!noosphere) return <Skeleton />;

  const coherencePercent = Math.round(noosphere.global_coherence * 100);

  return (
    <div className={`noosphere-widget ${noosphere.anomaly_detected ? 'anomaly' : ''}`}>
      <div className="header">
        <h3>Noosphere Velocity</h3>
        <span className={`status ${noosphere.status.toLowerCase()}`}>
          {noosphere.status}
        </span>
      </div>

      {/* Coherence Meter */}
      <div className="coherence-meter">
        <div className="meter-label">
          <span>Global Coherence</span>
          <span>{coherencePercent}%</span>
        </div>
        <div className="meter-bar">
          <div
            className="meter-fill"
            style={{
              width: `${coherencePercent}%`,
              background: noosphere.anomaly_detected
                ? 'linear-gradient(90deg, #f59e0b, #ef4444)'
                : '#22c55e'
            }}
          />
        </div>
      </div>

      {/* Anomaly Alert */}
      {noosphere.anomaly_detected && (
        <div className="anomaly-alert">
          <span className="strength">{noosphere.anomaly_strength}</span>
          <p>{noosphere.interpretation}</p>
          <span className="signal">{noosphere.betting_signal}</span>
        </div>
      )}

      {/* Module Status */}
      <div className="modules">
        {Object.entries(noosphere.modules).map(([key, mod]) => (
          <div key={key} className="module">
            <span className="module-name">{key.replace(/_/g, ' ')}</span>
            <span className={`module-signal signal-${mod.signal.toLowerCase().replace(' ', '-')}`}>
              {mod.signal}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 3. GANN Physics Display

### Endpoint: `/live/gann-physics-status`

**Response Schema:**
```json
{
  "status": "ACTIVE",
  "date": "2026-01-15",
  "modules": {
    "50_retracement": {
      "level": 61.2,
      "signal": "TREND CONTINUATION",
      "description": "Gravity check - markets tend to retrace 50%"
    },
    "rule_of_three": {
      "active": true,
      "signal": "EXHAUSTION",
      "description": "Third attempt usually fails or succeeds dramatically"
    },
    "annulifier_cycle": {
      "active": false,
      "signal": "NORMAL",
      "description": "7-day cycle completion - expect resolution"
    }
  },
  "overall_signal": "CONTINUATION",
  "timestamp": "2026-01-15T14:32:00"
}
```

### React Component

```jsx
function GannPhysicsCard() {
  const [gann, setGann] = useState(null);

  useEffect(() => {
    fetch('https://web-production-7b2a.up.railway.app/live/gann-physics-status')
      .then(r => r.json())
      .then(setGann);
  }, []);

  if (!gann) return <Skeleton />;

  return (
    <div className="gann-card">
      <div className="header">
        <h3>GANN Physics</h3>
        <span className={`overall-signal signal-${gann.overall_signal.toLowerCase()}`}>
          {gann.overall_signal}
        </span>
      </div>

      {/* 50% Retracement Gauge */}
      <div className="retracement-section">
        <h4>50% Retracement</h4>
        <div className="retracement-gauge">
          <div className="gauge-track">
            <div className="reversal-zone" style={{ left: '40%', width: '20%' }} />
            <div
              className="gauge-marker"
              style={{ left: `${gann.modules["50_retracement"].level}%` }}
            />
          </div>
          <div className="gauge-labels">
            <span>0%</span>
            <span className="zone-label">Reversal Zone</span>
            <span>100%</span>
          </div>
        </div>
        <p className="signal-text">{gann.modules["50_retracement"].signal}</p>
      </div>

      {/* Rule of Three */}
      <div className="rule-section">
        <div className={`rule-indicator ${gann.modules.rule_of_three.active ? 'active' : ''}`}>
          <span className="rule-name">Rule of Three</span>
          <span className="rule-signal">{gann.modules.rule_of_three.signal}</span>
        </div>
        <p className="description">{gann.modules.rule_of_three.description}</p>
      </div>

      {/* Annulifier Cycle */}
      <div className="cycle-section">
        <div className={`cycle-indicator ${gann.modules.annulifier_cycle.active ? 'active' : ''}`}>
          <span className="cycle-name">Annulifier Cycle</span>
          <span className="cycle-signal">{gann.modules.annulifier_cycle.signal}</span>
        </div>
        <p className="description">{gann.modules.annulifier_cycle.description}</p>
      </div>
    </div>
  );
}
```

---

## 4. Astrological Status

### Endpoint: `/live/astro-status`

**Response Schema:**
```json
{
  "overall_score": 62.5,
  "rating": "FAVORABLE",
  "moon_phase": {
    "phase_name": "Waning Crescent",
    "illumination": 14.9
  },
  "planetary_hour": {
    "hour_ruler": "Mars",
    "quality": "AGGRESSIVE",
    "hour_number": 5
  },
  "nakshatra": {
    "nakshatra_name": "Mula",
    "nakshatra_number": 19,
    "deity": "Nirriti",
    "quality": "Sharp/Dreadful"
  },
  "retrogrades": {
    "mercury": { "is_retrograde": false },
    "venus": { "is_retrograde": false },
    "mars": { "is_retrograde": false }
  },
  "timestamp": "2026-01-15T14:32:00"
}
```

### React Component

```jsx
function AstroStatusCard() {
  const [astro, setAstro] = useState(null);

  useEffect(() => {
    fetch('https://web-production-7b2a.up.railway.app/live/astro-status')
      .then(r => r.json())
      .then(setAstro);
  }, []);

  if (!astro) return <Skeleton />;

  const ratingColors = {
    FAVORABLE: '#22c55e',
    NEUTRAL: '#eab308',
    UNFAVORABLE: '#ef4444'
  };

  return (
    <div className="astro-card">
      <div className="header">
        <h3>Astro Status</h3>
        <div className="score-badge" style={{ background: ratingColors[astro.rating] }}>
          {astro.overall_score.toFixed(0)}
        </div>
      </div>

      {/* Moon Phase */}
      <div className="section">
        <div className="moon-visual">
          <MoonPhaseIcon
            phase={astro.moon_phase.phase_name}
            illumination={astro.moon_phase.illumination}
          />
        </div>
        <div className="moon-info">
          <span className="phase-name">{astro.moon_phase.phase_name}</span>
          <span className="illumination">{astro.moon_phase.illumination}% illuminated</span>
        </div>
      </div>

      {/* Planetary Hour */}
      <div className="section planetary-hour">
        <span className="label">Planetary Hour</span>
        <div className="ruler-badge">
          <PlanetIcon planet={astro.planetary_hour.hour_ruler} />
          <span>{astro.planetary_hour.hour_ruler}</span>
        </div>
        <span className={`quality quality-${astro.planetary_hour.quality.toLowerCase()}`}>
          {astro.planetary_hour.quality}
        </span>
      </div>

      {/* Nakshatra */}
      <div className="section nakshatra">
        <span className="label">Nakshatra (Lunar Mansion)</span>
        <span className="name">{astro.nakshatra.nakshatra_name}</span>
        <span className="deity">Deity: {astro.nakshatra.deity}</span>
        <span className="quality">{astro.nakshatra.quality}</span>
      </div>

      {/* Retrogrades */}
      <div className="section retrogrades">
        <span className="label">Retrograde Status</span>
        <div className="planet-status">
          {Object.entries(astro.retrogrades).map(([planet, status]) => (
            <div
              key={planet}
              className={`planet ${status.is_retrograde ? 'retrograde' : 'direct'}`}
            >
              <PlanetIcon planet={planet} />
              <span>{planet}</span>
              <span className="status-text">
                {status.is_retrograde ? '℞ Rx' : 'Direct'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## 5. Full Esoteric Edge Panel

### Endpoint: `/live/esoteric-edge`

**Response Schema:**
```json
{
  "timestamp": "2026-01-15T14:32:00Z",
  "daily_energy": {
    "betting_outlook": "FAVORABLE",
    "overall_energy": 7.0,
    "moon_phase": "sagittarius",
    "void_moon": {
      "is_void": false,
      "moon_sign": "Sagittarius",
      "degree_in_sign": 13.24,
      "phase": "Waning Crescent",
      "illumination": 14.9
    },
    "schumann_frequency": { "current_hz": 7.83, "status": "NORMAL" },
    "planetary_hours": { "current_hour": 5, "ruler": "Mars", "quality": "AGGRESSIVE" }
  },
  "game_signals": [
    {
      "game_id": "sample1",
      "home_team": "Lakers",
      "away_team": "Celtics",
      "signals": {
        "founders_echo": { "home_match": 0.85, "away_match": 0.92, "boost": 0.35 },
        "gann_square": { "spread_angle": 45, "resonant": true },
        "atmospheric": { "elevation_factor": 0.95, "pressure_hpa": 1013 }
      }
    }
  ],
  "prop_signals": [
    {
      "player_id": "lebron_james",
      "player_name": "LeBron James",
      "signals": {
        "biorhythms": { "physical": -97.9, "emotional": 62.3, "intellectual": 99.0 },
        "life_path_sync": { "player_life_path": 1, "jersey_number": 23, "sync_score": 75 }
      }
    }
  ],
  "noosphere": { "velocity": 68.5, "trend": "RISING", "signal": "MOMENTUM_BUILD" }
}
```

### React Page Component

```jsx
function EsotericEdgePage() {
  const [esoteric, setEsoteric] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('https://web-production-7b2a.up.railway.app/live/esoteric-edge')
      .then(r => r.json())
      .then(data => {
        setEsoteric(data);
        setLoading(false);
      });
  }, []);

  if (loading) return <LoadingScreen />;

  return (
    <div className="esoteric-page">
      <header className="page-header">
        <h1>Esoteric Edge</h1>
        <span className="timestamp">{new Date(esoteric.timestamp).toLocaleString()}</span>
      </header>

      {/* Daily Energy Section */}
      <section className="daily-section">
        <h2>Daily Energy</h2>
        <div className="energy-grid">
          <EnergyScoreCard energy={esoteric.daily_energy} />
          <VoidMoonCard voidMoon={esoteric.daily_energy.void_moon} />
          <PlanetaryHourCard hours={esoteric.daily_energy.planetary_hours} />
          <SchumannCard schumann={esoteric.daily_energy.schumann_frequency} />
        </div>
      </section>

      {/* Game Signals Section */}
      <section className="games-section">
        <h2>Game Signals</h2>
        <div className="games-grid">
          {esoteric.game_signals.map(game => (
            <GameSignalCard key={game.game_id} game={game} />
          ))}
        </div>
      </section>

      {/* Player Prop Signals */}
      <section className="props-section">
        <h2>Player Biorhythms</h2>
        <div className="props-grid">
          {esoteric.prop_signals.map(player => (
            <PlayerBioCard key={player.player_id} player={player} />
          ))}
        </div>
      </section>

      {/* Noosphere */}
      <section className="noosphere-section">
        <h2>Noosphere Velocity</h2>
        <NoosphereDisplay noosphere={esoteric.noosphere} />
      </section>
    </div>
  );
}
```

---

## 6. Player Biorhythm Card

### Component

```jsx
function PlayerBioCard({ player }) {
  const { biorhythms, life_path_sync } = player.signals;

  const getBioColor = (value) => {
    if (value > 50) return '#22c55e';
    if (value > 0) return '#eab308';
    if (value > -50) return '#f97316';
    return '#ef4444';
  };

  return (
    <div className="player-bio-card">
      <div className="player-header">
        <span className="player-name">{player.player_name}</span>
        <span className="life-path">LP: {life_path_sync.player_life_path}</span>
      </div>

      {/* Biorhythm Bars */}
      <div className="biorhythm-bars">
        {[
          { name: 'Physical', value: biorhythms.physical, icon: '💪' },
          { name: 'Emotional', value: biorhythms.emotional, icon: '❤️' },
          { name: 'Intellectual', value: biorhythms.intellectual, icon: '🧠' }
        ].map(({ name, value, icon }) => (
          <div key={name} className="bio-bar-row">
            <span className="bio-label">{icon} {name}</span>
            <div className="bio-bar">
              <div
                className="bio-fill"
                style={{
                  width: `${Math.abs(value) / 2}%`,
                  marginLeft: value < 0 ? `${50 - Math.abs(value) / 2}%` : '50%',
                  background: getBioColor(value)
                }}
              />
              <div className="bio-center-line" />
            </div>
            <span className="bio-value" style={{ color: getBioColor(value) }}>
              {value.toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {/* Life Path Sync */}
      <div className="sync-section">
        <span className="sync-label">Jersey #{life_path_sync.jersey_number}</span>
        <div className="sync-meter">
          <div
            className="sync-fill"
            style={{ width: `${life_path_sync.sync_score}%` }}
          />
        </div>
        <span className="sync-score">{life_path_sync.sync_score}% sync</span>
      </div>
    </div>
  );
}
```

---

## 7. Void Moon Warning Banner

### Component

```jsx
function VoidMoonBanner({ voidMoon }) {
  if (!voidMoon?.is_void) return null;

  return (
    <div className="void-moon-banner">
      <div className="banner-icon">🌑</div>
      <div className="banner-content">
        <h4>Void of Course Moon Active</h4>
        <p>Moon in {voidMoon.moon_sign} ({voidMoon.degree_in_sign.toFixed(1)}°)</p>
        <p className="time-range">{voidMoon.void_start} - {voidMoon.void_end}</p>
        <p className="warning">{voidMoon.warning}</p>
      </div>
      <div className="banner-action">
        <span className="next-sign">Next: {voidMoon.next_sign}</span>
        <span className="hours-left">{voidMoon.hours_until_sign_change.toFixed(1)}h remaining</span>
      </div>
    </div>
  );
}
```

---

## 8. API Helper Functions (esotericApi.js)

```javascript
const API_BASE = 'https://web-production-7b2a.up.railway.app';

export const esotericApi = {
  // Daily Energy
  getTodayEnergy: () =>
    fetch(`${API_BASE}/esoteric/today-energy`).then(r => r.json()),

  // Full Esoteric Edge
  getEsotericEdge: () =>
    fetch(`${API_BASE}/live/esoteric-edge`).then(r => r.json()),

  // Noosphere Status
  getNoosphereStatus: () =>
    fetch(`${API_BASE}/live/noosphere/status`).then(r => r.json()),

  // GANN Physics
  getGannPhysics: () =>
    fetch(`${API_BASE}/live/gann-physics-status`).then(r => r.json()),

  // Astro Status
  getAstroStatus: () =>
    fetch(`${API_BASE}/live/astro-status`).then(r => r.json()),

  // Planetary Hour
  getPlanetaryHour: () =>
    fetch(`${API_BASE}/live/planetary-hour`).then(r => r.json()),

  // Nakshatra
  getNakshatra: () =>
    fetch(`${API_BASE}/live/nakshatra`).then(r => r.json()),

  // Retrograde Status
  getRetrogradeStatus: () =>
    fetch(`${API_BASE}/live/retrograde-status`).then(r => r.json()),

  // Complete Analysis for a Pick
  getPickAnalysis: (params) =>
    fetch(`${API_BASE}/live/esoteric-analysis?${new URLSearchParams(params)}`).then(r => r.json()),
};

// Example: Get analysis for a specific pick
// esotericApi.getPickAnalysis({
//   player: 'LeBron James',
//   team: 'Lakers',
//   opponent: 'Celtics',
//   spread: -3.5,
//   total: 225,
//   public_pct: 65,
//   model_probability: 58
// })
```

---

## 9. Design System Colors

```css
:root {
  /* Outlook Colors */
  --favorable: #22c55e;
  --neutral: #eab308;
  --cautious: #ef4444;

  /* Moon Phases */
  --new-moon: #1a1a2e;
  --waxing: #3b82f6;
  --full-moon: #fbbf24;
  --waning: #8b5cf6;

  /* Planets */
  --sun: #fbbf24;
  --moon: #94a3b8;
  --mars: #ef4444;
  --mercury: #a78bfa;
  --jupiter: #f97316;
  --venus: #ec4899;
  --saturn: #6b7280;

  /* Backgrounds */
  --esoteric-bg: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  --card-bg: rgba(255, 255, 255, 0.05);

  /* Signals */
  --signal-positive: #22c55e;
  --signal-negative: #ef4444;
  --signal-neutral: #6b7280;
}
```

---

## 10. Testing Endpoints

```bash
# Daily Energy
curl https://web-production-7b2a.up.railway.app/esoteric/today-energy

# Full Esoteric Edge
curl https://web-production-7b2a.up.railway.app/live/esoteric-edge

# Noosphere
curl https://web-production-7b2a.up.railway.app/live/noosphere/status

# GANN Physics
curl https://web-production-7b2a.up.railway.app/live/gann-physics-status

# Astro Status
curl https://web-production-7b2a.up.railway.app/live/astro-status

# Planetary Hour
curl https://web-production-7b2a.up.railway.app/live/planetary-hour

# Nakshatra
curl https://web-production-7b2a.up.railway.app/live/nakshatra

# Retrograde
curl https://web-production-7b2a.up.railway.app/live/retrograde-status

# Pick Analysis
curl "https://web-production-7b2a.up.railway.app/live/esoteric-analysis?player=LeBron%20James&team=Lakers&spread=-3.5&total=225"
```

---

## Player Database

The backend now includes **233 real player birth dates** across all 5 sports:
- **NBA:** 92 players (all teams represented)
- **NFL:** 48 players (QBs, RBs, WRs, TEs)
- **MLB:** 39 players (hitters & pitchers)
- **NHL:** 40 players (forwards, D, goalies)
- **NCAAB:** 14 players (top prospects)

Biorhythm and life path calculations now use **real birth data**.

---

## Moon Calculations

The backend uses **astronomical ephemeris** for accurate moon data:
- Moon sign accurate to ~0.5 degrees
- Real phase illumination percentages
- Void of course estimation from position
- Nakshatra (lunar mansion) calculations

---

*Handoff Version: 1.0*
*Backend: v14.8*
*Date: 2026-01-15*
