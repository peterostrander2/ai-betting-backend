# Frontend Handoff - v10.34 Health Fields & Missing UI Features

**Date:** 2026-01-21
**Backend Version:** v10.34 (production_v10.33+)
**Frontend Repo:** bookie-member-app
**Priority:** P0-P4 fixes for frontend sync

---

## Overview

The backend now returns v10.34 health fields that enable the frontend to show database sync status. This document provides complete code for implementing:

1. **P0**: Fix api.js to preserve new health fields
2. **P1**: Add DB sync health indicator to SmashSpotsPage
3. **P2**: Use consolidated endpoints for faster loads
4. **P3**: Add dev tools panel (debug toggle, raw viewer)
5. **P4**: Add transparency/performance dashboard

---

## P0: Fix api.js to Preserve Health Fields (10 min)

### Problem

The frontend api.js is stripping the new v10.34 health fields from the `/live/best-bets/{sport}` response.

### Backend Response (v10.34)

```json
{
  "sport": "NBA",
  "source": "production_v10.33",
  "picks": [...],
  "props": {...},
  "game_picks": {...},
  "esoteric": {...},
  "api_status": {...},
  "data_message": "...",
  "timestamp": "2026-01-21T...",
  "database_available": true,
  "picks_saved": 10,
  "signals_saved": 45
}
```

### Fix: Update api.js getBestBets()

Find the `getBestBets` function in your api.js and update it to preserve these fields:

```javascript
// api.js - getBestBets function

async getBestBets(sport, options = {}) {
  const { debug = false, minConfidence = null } = options;

  let url = `${this.baseUrl}/live/best-bets/${sport}`;
  const params = new URLSearchParams();
  if (debug) params.append('debug', '1');
  if (minConfidence) params.append('min_confidence', minConfidence);
  if (params.toString()) url += `?${params.toString()}`;

  const response = await this.fetch(url);
  const data = await response.json();

  // v10.34: Preserve ALL fields from backend response
  // DO NOT destructure and rebuild - pass through entire response
  return {
    ...data,
    // Ensure these v10.34 fields are explicitly preserved
    database_available: data.database_available ?? false,
    picks_saved: data.picks_saved ?? 0,
    signals_saved: data.signals_saved ?? 0,
    // Flatten picks for easy access (backward compatibility)
    picks: data.picks || [],
    props: data.props || { picks: [], count: 0 },
    game_picks: data.game_picks || { picks: [], count: 0 },
  };
}
```

### Verification

After deploying, check browser console:
```javascript
const data = await api.getBestBets('nba');
console.log('DB Status:', {
  database_available: data.database_available,
  picks_saved: data.picks_saved,
  signals_saved: data.signals_saved
});
```

---

## P1: Add Health Indicator to SmashSpotsPage (30 min)

### Component: DBSyncIndicator.jsx

Create a new component to show database sync status:

```jsx
// components/DBSyncIndicator.jsx

import React from 'react';

const DBSyncIndicator = ({ databaseAvailable, picksSaved, signalsSaved }) => {
  // Determine sync status
  const getSyncStatus = () => {
    if (!databaseAvailable) {
      return { color: 'red', icon: '🔴', text: 'DB Offline' };
    }
    if (picksSaved === 0 && signalsSaved === 0) {
      return { color: 'yellow', icon: '🟡', text: 'DB Connected (No Saves)' };
    }
    return { color: 'green', icon: '🟢', text: 'DB Synced' };
  };

  const status = getSyncStatus();

  return (
    <div
      className="db-sync-indicator"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '4px 12px',
        borderRadius: '16px',
        backgroundColor: status.color === 'green' ? '#e8f5e9' :
                         status.color === 'yellow' ? '#fff3e0' : '#ffebee',
        fontSize: '12px',
        fontWeight: '500'
      }}
    >
      <span>{status.icon}</span>
      <span>{status.text}</span>
      {picksSaved > 0 && (
        <span style={{ color: '#666' }}>
          ({picksSaved} picks, {signalsSaved} signals)
        </span>
      )}
    </div>
  );
};

export default DBSyncIndicator;
```

### Integration: SmashSpotsPage.jsx

Add the indicator to your SmashSpotsPage:

```jsx
// In SmashSpotsPage.jsx

import DBSyncIndicator from './components/DBSyncIndicator';

// In your component, after fetching best-bets:
const [dbHealth, setDbHealth] = useState({
  database_available: false,
  picks_saved: 0,
  signals_saved: 0
});

// When fetching data:
const fetchBestBets = async () => {
  const data = await api.getBestBets(sport);
  setPicks(data.picks);

  // v10.34: Capture DB health from response
  setDbHealth({
    database_available: data.database_available,
    picks_saved: data.picks_saved,
    signals_saved: data.signals_saved
  });
};

// In your JSX, add near the header:
<div className="page-header">
  <h1>SMASH Spots - {sport.toUpperCase()}</h1>
  <DBSyncIndicator
    databaseAvailable={dbHealth.database_available}
    picksSaved={dbHealth.picks_saved}
    signalsSaved={dbHealth.signals_saved}
  />
</div>
```

---

## P2: Use Consolidated Endpoints for Faster Loads (1 hour)

### Current Problem

Dashboard loads make 6+ sequential API calls:
```
/live/best-bets/nba     → 200ms
/live/splits/nba        → 150ms
/live/lines/nba         → 180ms
/live/injuries/nba      → 160ms
/live/sharp/nba         → 140ms
/live/props/nba         → 200ms
─────────────────────────────────
Total: ~1000ms (waterfall)
```

### Solution: Use /live/sport-dashboard/{sport}

Single consolidated endpoint that fetches all data server-side in parallel:

```
/live/sport-dashboard/nba → 250ms (all data)
```

### api.js: Add getSportDashboard()

```javascript
// api.js - Add new consolidated method

async getSportDashboard(sport) {
  const response = await this.fetch(`${this.baseUrl}/live/sport-dashboard/${sport}`);
  const data = await response.json();

  return {
    // All nested data
    bestBets: data.best_bets || { props: [], game_picks: [] },
    marketOverview: {
      lines: data.market_overview?.lines || [],
      splits: data.market_overview?.splits || [],
      sharpSignals: data.market_overview?.sharp_signals || []
    },
    context: {
      injuries: data.context?.injuries || []
    },
    dailyEnergy: data.daily_energy || {},
    // v10.34 health fields
    database_available: data.database_available ?? false,
    picks_saved: data.picks_saved ?? 0,
    signals_saved: data.signals_saved ?? 0,
    // Meta
    timestamp: data.timestamp,
    cacheInfo: data.cache_info
  };
}
```

### SmashSpotsPage.jsx: Update to Use Consolidated Endpoint

```jsx
// Before (6 calls):
const bestBets = await api.getBestBets(sport);
const splits = await api.getSplits(sport);
const lines = await api.getLines(sport);
const injuries = await api.getInjuries(sport);
const sharp = await api.getSharp(sport);

// After (1 call):
const dashboard = await api.getSportDashboard(sport);

// Access data from consolidated response:
const bestBets = dashboard.bestBets;
const splits = dashboard.marketOverview.splits;
const lines = dashboard.marketOverview.lines;
const sharp = dashboard.marketOverview.sharpSignals;
const injuries = dashboard.context.injuries;
```

### Other Consolidated Endpoints

| Endpoint | Use Case | Replaces |
|----------|----------|----------|
| `/live/sport-dashboard/{sport}` | Dashboard page load | 6 endpoints |
| `/live/game-details/{sport}/{game_id}` | Game detail modal | 5 endpoints |
| `/live/parlay-builder-init/{sport}?user_id=X` | Parlay builder init | 3 endpoints |

---

## P3: Add Dev Tools Panel (2 hours)

### Component: DevToolsPanel.jsx

```jsx
// components/DevToolsPanel.jsx

import React, { useState } from 'react';

const DevToolsPanel = ({ onDebugToggle, onRefresh }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [debugMode, setDebugMode] = useState(false);
  const [rawResponse, setRawResponse] = useState(null);

  const handleDebugToggle = () => {
    const newMode = !debugMode;
    setDebugMode(newMode);
    onDebugToggle(newMode);
  };

  const fetchRawResponse = async () => {
    const response = await fetch('/live/best-bets/nba?debug=1', {
      headers: { 'X-API-Key': 'YOUR_API_KEY' }
    });
    const data = await response.json();
    setRawResponse(data);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          padding: '8px 16px',
          backgroundColor: '#333',
          color: '#fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          zIndex: 9999
        }}
      >
        Dev Tools
      </button>
    );
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        width: '400px',
        maxHeight: '500px',
        backgroundColor: '#1a1a2e',
        color: '#eee',
        borderRadius: '8px',
        padding: '16px',
        zIndex: 9999,
        overflow: 'auto'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
        <h3 style={{ margin: 0 }}>Dev Tools</h3>
        <button onClick={() => setIsOpen(false)}>Close</button>
      </div>

      {/* Debug Toggle */}
      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="checkbox"
            checked={debugMode}
            onChange={handleDebugToggle}
          />
          Enable Debug Mode (?debug=1)
        </label>
      </div>

      {/* Raw Response Viewer */}
      <div style={{ marginBottom: '16px' }}>
        <button onClick={fetchRawResponse} style={{ marginBottom: '8px' }}>
          Fetch Raw Response
        </button>
        {rawResponse && (
          <pre style={{
            backgroundColor: '#0d0d1a',
            padding: '12px',
            borderRadius: '4px',
            fontSize: '11px',
            maxHeight: '300px',
            overflow: 'auto'
          }}>
            {JSON.stringify(rawResponse, null, 2)}
          </pre>
        )}
      </div>

      {/* Debug Info Display */}
      {rawResponse?.debug && (
        <div>
          <h4>Debug Info</h4>
          <table style={{ width: '100%', fontSize: '12px' }}>
            <tbody>
              <tr>
                <td>Games Pulled:</td>
                <td>{rawResponse.debug.games_pulled}</td>
              </tr>
              <tr>
                <td>Props Scored:</td>
                <td>{rawResponse.debug.props_scored}</td>
              </tr>
              <tr>
                <td>Gold Star Props:</td>
                <td>{rawResponse.debug.gold_star_props}</td>
              </tr>
              <tr>
                <td>DB Enabled Live:</td>
                <td>{rawResponse.debug.db_enabled_live ? 'Yes' : 'No'}</td>
              </tr>
              <tr>
                <td>Picks Saved:</td>
                <td>{rawResponse.debug.picks_saved_to_ledger}</td>
              </tr>
              <tr>
                <td>Signals Saved:</td>
                <td>{rawResponse.debug.signals_saved_to_ledger}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default DevToolsPanel;
```

### Usage in App.jsx

```jsx
// Only show in development
{process.env.NODE_ENV === 'development' && (
  <DevToolsPanel
    onDebugToggle={(debug) => setDebugMode(debug)}
    onRefresh={() => fetchData()}
  />
)}
```

---

## P4: Transparency & Performance Dashboard (4 hours)

### New Backend Endpoints to Use

| Endpoint | Purpose |
|----------|---------|
| `/live/signal-report?sport=NBA` | Signal attribution & transparency |
| `/live/signal-uplift/{sport}` | Which signals improve picks |
| `/live/grader/performance/{sport}` | Hit rate & MAE metrics |
| `/live/grader/daily-report` | Daily performance summary |
| `/live/api-health` | API quota status |
| `/live/cache/stats` | Cache hit rates |

### Component: PerformanceDashboard.jsx

```jsx
// pages/PerformanceDashboard.jsx

import React, { useState, useEffect } from 'react';

const PerformanceDashboard = () => {
  const [performance, setPerformance] = useState(null);
  const [dailyReport, setDailyReport] = useState(null);
  const [apiHealth, setApiHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [perfRes, reportRes, healthRes] = await Promise.all([
        fetch('/live/grader/performance/nba?days_back=7'),
        fetch('/live/grader/daily-report'),
        fetch('/live/api-health')
      ]);

      setPerformance(await perfRes.json());
      setDailyReport(await reportRes.json());
      setApiHealth(await healthRes.json());
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    }
    setLoading(false);
  };

  if (loading) return <div>Loading performance data...</div>;

  return (
    <div className="performance-dashboard">
      <h1>System Performance</h1>

      {/* Daily Report Card */}
      <div className="card">
        <h2>Daily Report</h2>
        <pre style={{ whiteSpace: 'pre-wrap' }}>
          {dailyReport?.report || 'No report available'}
        </pre>
      </div>

      {/* Performance Metrics */}
      <div className="card">
        <h2>7-Day Performance</h2>
        {performance && (
          <div className="metrics-grid">
            <div className="metric">
              <span className="value">{performance.total_picks || 0}</span>
              <span className="label">Total Picks</span>
            </div>
            <div className="metric">
              <span className="value">{performance.wins || 0}-{performance.losses || 0}</span>
              <span className="label">Record</span>
            </div>
            <div className="metric">
              <span className="value">{((performance.hit_rate || 0) * 100).toFixed(1)}%</span>
              <span className="label">Hit Rate</span>
            </div>
            <div className="metric">
              <span className="value">{performance.roi?.toFixed(1) || 0}%</span>
              <span className="label">ROI</span>
            </div>
          </div>
        )}
      </div>

      {/* API Health */}
      <div className="card">
        <h2>API Health</h2>
        {apiHealth && (
          <div className="api-status">
            <div className={`status-badge ${apiHealth.overall_status}`}>
              {apiHealth.overall_status}
            </div>
            <p>{apiHealth.summary}</p>
            {apiHealth.alerts?.length > 0 && (
              <ul className="alerts">
                {apiHealth.alerts.map((alert, i) => (
                  <li key={i}>{alert}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PerformanceDashboard;
```

### Add Route

```jsx
// In your router config:
<Route path="/performance" element={<PerformanceDashboard />} />
```

---

## Quick Reference: v10.34 Response Schema

### /live/best-bets/{sport} Response

```json
{
  "sport": "NBA",
  "source": "production_v10.33",
  "scoring_system": "v10.33: Top-level DB health fields + Auto-grading + Daily Transparency",

  "picks": [
    {
      "player_name": "LeBron James",
      "stat_type": "player_assists",
      "line": 7.5,
      "over_under": "over",
      "odds": -140,
      "smash_score": 7.8,
      "tier": "GOLD_STAR",
      "confidence": "HIGH",
      "confidence_grade": "A",
      "units": 2.0,
      "badges": ["SHARP_MONEY", "JARVIS_TRIGGER", "GOLDILOCKS"],
      "reasons": [
        "RESEARCH: Sharp Split (Props) +1.0",
        "RESEARCH: Reverse Line Move +1.0",
        "ESOTERIC: Jarvis Trigger 33 +0.4"
      ],
      "fired_signals": ["SHARP_SPLIT_PROPS", "RLM", "JARVIS_33"],
      "fired_signal_count": 3,
      "jarvis_analysis": {...}
    }
  ],

  "props": {
    "count": 10,
    "total_analyzed": 45,
    "picks": [...]
  },

  "game_picks": {
    "count": 5,
    "total_analyzed": 8,
    "picks": [...]
  },

  "esoteric": {
    "daily_energy": {...},
    "astro_status": {...},
    "learned_weights": {...},
    "learning_active": true
  },

  "api_status": {
    "odds_api_configured": true,
    "playbook_api_configured": true,
    "props_source": "odds_api",
    "sharp_source": "playbook"
  },

  "data_message": "Live data retrieved: 10 prop picks, 5 game picks",
  "timestamp": "2026-01-21T14:30:00.000Z",

  "database_available": true,
  "picks_saved": 15,
  "signals_saved": 45
}
```

### Debug Mode (?debug=1)

When debug=1 is passed, additional fields are included:

```json
{
  "debug": {
    "games_pulled": 8,
    "candidates_scored": 85,
    "props_scored": 60,
    "props_deduped": 5,
    "returned_picks": 15,
    "gold_star_props": 3,
    "gold_star_games": 2,
    "volume_governor_applied": false,
    "db_enabled_live": true,
    "picks_saved_to_ledger": 15,
    "signals_saved_to_ledger": 45,
    "picks_attempted_save": 15,
    "db_error": null,
    "save_errors": null
  }
}
```

---

## Testing Checklist

After implementing these changes, verify:

- [ ] `api.getBestBets('nba')` returns `database_available`, `picks_saved`, `signals_saved`
- [ ] DBSyncIndicator shows correct status (green/yellow/red)
- [ ] `api.getSportDashboard('nba')` returns all consolidated data
- [ ] DevToolsPanel shows debug info when debug mode enabled
- [ ] PerformanceDashboard loads and displays metrics

---

## GitHub Quick Links

**Edit api.js directly:**
https://github.com/peterostrander2/bookie-member-app/edit/main/src/services/api.js

**Create new component:**
https://github.com/peterostrander2/bookie-member-app/new/main/src/components

---

*Last Updated: 2026-01-21*
*Backend Version: v10.34 (production_v10.33+)*
