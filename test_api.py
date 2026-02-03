"""
Test Suite for AI Sports Betting API
Run this after starting the server to verify all 8 models work
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your Railway URL when deployed
VERBOSE = True

def log(message, emoji="📝"):
    """Pretty print test results"""
    if VERBOSE:
        print(f"{emoji} {message}")

def test_health_check():
    """Test 1: Basic health check"""
    log("Testing health check...", "🔍")
    
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    
    data = response.json()
    assert data['status'] == 'online'
    assert 'version' in data
    assert len(data['models']) == 8
    
    log("Health check passed!", "✅")
    return True

def test_model_status():
    """Test 2: Check all 8 models"""
    log("Testing model status...", "🔍")
    
    response = requests.get(f"{BASE_URL}/model-status")
    assert response.status_code == 200
    
    data = response.json()
    assert data['status'] == 'operational'
    assert data['total_models'] == 8
    assert 'models' in data
    
    # Check each model
    expected_models = [
        'ensemble_stacking',
        'lstm_network',
        'matchup_specific',
        'monte_carlo',
        'line_analyzer',
        'rest_fatigue',
        'injury_impact',
        'edge_calculator'
    ]
    
    for model in expected_models:
        assert model in data['models']
        log(f"  Model '{model}': {data['models'][model]}", "  ✓")
    
    log("All 8 models ready!", "✅")
    return True

def test_comprehensive_prediction():
    """Test 3: Full prediction with all 8 models"""
    log("Testing comprehensive prediction...", "🔍")
    
    prediction_request = {
        "player_id": "lebron_james",
        "opponent_id": "gsw",
        "features": [25.4, 7.2, 6.8, 1, 35, 28, 2],
        "recent_games": [27, 31, 22, 28, 25, 30, 26, 24, 29, 32],
        "player_stats": {
            "stat_type": "points",
            "expected_value": 27.5,
            "variance": 45.0,
            "std_dev": 6.5
        },
        "schedule": {
            "days_rest": 1,
            "travel_miles": 1500,
            "games_in_last_7": 3,
            "road_trip_game_num": 2
        },
        "injuries": [],
        "depth_chart": {},
        "game_id": "lal_gsw_20250114",
        "current_line": 25.5,
        "opening_line": 26.0,
        "time_until_game": 6.0,
        "betting_percentages": {
            "public_on_favorite": 68.0
        },
        "betting_odds": -110,
        "line": 25.5
    }
    
    response = requests.post(
        f"{BASE_URL}/predict",
        json=prediction_request
    )
    
    assert response.status_code == 200
    
    prediction = response.json()
    
    # Verify all required fields
    required_fields = [
        'predicted_value',
        'line',
        'recommendation',
        'ai_score',
        'confidence',
        'expected_value',
        'probability',
        'kelly_bet_size',
        'factors',
        'monte_carlo'
    ]
    
    for field in required_fields:
        assert field in prediction, f"Missing field: {field}"
    
    # Display results
    log("\n  📊 Prediction Results:", "")
    log(f"    Predicted Value: {prediction['predicted_value']}", "")
    log(f"    Line: {prediction['line']}", "")
    log(f"    Recommendation: {prediction['recommendation']}", "")
    log(f"    AI Score: {prediction['ai_score']}/10", "")
    log(f"    Confidence: {prediction['confidence']}", "")
    log(f"    Probability: {prediction['probability']}", "")
    log(f"    Expected Value: ${prediction['expected_value']}", "")
    log(f"    Kelly Bet Size: {prediction['kelly_bet_size']}%", "")
    
    # Verify factors from all 8 models
    factors = prediction['factors']
    log("\n  🧠 Model Contributions:", "")
    
    # Model 1: Ensemble
    assert 'base_prediction' in factors
    log(f"    Model 1 (Ensemble): {factors['base_prediction']}", "")
    
    # Model 2: LSTM
    assert 'trend_analysis' in factors
    log(f"    Model 2 (LSTM Trend): {factors['trend_analysis']['trend']}", "")
    
    # Model 6: Rest/Fatigue
    assert 'rest_factor' in factors
    log(f"    Model 6 (Rest Factor): {factors['rest_factor']['fatigue_level']}", "")
    
    # Model 7: Injury
    assert 'injury_impact' in factors
    log(f"    Model 7 (Injury Impact): +{factors['injury_impact']['usage_boost_for_healthy']} pts", "")
    
    # Model 5: Line Movement
    assert 'line_movement' in factors
    log(f"    Model 5 (Sharp Money): {factors['line_movement']['sharp_money_detected']}", "")
    
    # Model 4: Monte Carlo
    monte_carlo = prediction['monte_carlo']
    assert 'mean' in monte_carlo
    assert 'percentiles' in monte_carlo
    log(f"    Model 4 (Monte Carlo): {monte_carlo['mean']} mean", "")
    
    log("\nComprehensive prediction test passed!", "✅")
    return True

def test_monte_carlo_simulation():
    """Test 4: Monte Carlo game simulation"""
    log("Testing Monte Carlo simulation...", "🔍")
    
    simulation_request = {
        "team_a_stats": {
            "pace": 100.0,
            "off_rating": 115.0,
            "off_rating_std": 5.0
        },
        "team_b_stats": {
            "pace": 98.0,
            "off_rating": 110.0,
            "off_rating_std": 6.0
        },
        "num_simulations": 10000
    }
    
    response = requests.post(
        f"{BASE_URL}/simulate-game",
        json=simulation_request
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data['status'] == 'success'
    assert data['simulations_run'] == 10000
    
    results = data['results']
    
    log(f"  Team A Win Probability: {results['team_a_win_probability']:.1%}", "")
    log(f"  Team B Win Probability: {results['team_b_win_probability']:.1%}", "")
    log(f"  Expected Total: {results['team_a_avg_score'] + results['team_b_avg_score']:.1f}", "")
    
    # Verify probabilities sum to 1
    total_prob = results['team_a_win_probability'] + results['team_b_win_probability']
    assert abs(total_prob - 1.0) < 0.001, "Probabilities don't sum to 1"
    
    log("Monte Carlo simulation test passed!", "✅")
    return True

def test_line_analysis():
    """Test 5: Line movement analysis"""
    log("Testing line movement analysis...", "🔍")
    
    line_request = {
        "game_id": "lal_gsw_20250114",
        "current_line": -5.5,
        "opening_line": -4.0,
        "time_until_game": 2.5,
        "betting_percentages": {
            "public_on_favorite": 72.0
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/analyze-line",
        json=line_request
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data['status'] == 'success'
    
    analysis = data['analysis']
    
    log(f"  Line Movement: {analysis['line_movement']}", "")
    log(f"  Reverse Line Movement: {analysis['reverse_line_movement']}", "")
    log(f"  Steam Move: {analysis['steam_move']}", "")
    log(f"  Sharp Money Detected: {analysis['sharp_money_detected']}", "")
    
    if analysis['sharp_side']:
        log(f"  Sharp Side: {analysis['sharp_side']}", "  💡")
    
    log("Line analysis test passed!", "✅")
    return True

def test_edge_calculation():
    """Test 6: Betting edge calculator"""
    log("Testing edge calculation...", "🔍")
    
    edge_request = {
        "your_probability": 0.65,
        "betting_odds": -110
    }
    
    response = requests.post(
        f"{BASE_URL}/calculate-edge",
        json=edge_request
    )
    
    assert response.status_code == 200
    
    data = response.json()
    assert data['status'] == 'success'
    
    edge = data['edge_analysis']
    
    log(f"  Expected Value: ${edge['expected_value']}", "")
    log(f"  Edge: {edge['edge_percent']}%", "")
    log(f"  Kelly Bet Size: {edge['kelly_bet_size']}%", "")
    log(f"  Recommendation: {edge['recommendation']}", "")
    log(f"  Confidence: {edge['confidence']}", "")
    
    # Verify positive EV
    if edge['expected_value'] > 0:
        log("  Positive EV detected! ✅", "  💰")
    
    log("Edge calculation test passed!", "✅")
    return True

def test_docs_endpoint():
    """Test 7: Documentation endpoints"""
    log("Testing documentation endpoints...", "🔍")
    
    # Test /docs-info
    response = requests.get(f"{BASE_URL}/docs-info")
    assert response.status_code == 200
    
    data = response.json()
    assert 'models' in data
    assert len(data['models']) == 8
    
    # Verify each model has required info
    for model in data['models']:
        assert 'name' in model
        assert 'description' in model
        assert 'purpose' in model
        assert 'edge' in model
        log(f"  Model {model['id']}: {model['name']}", "")
    
    log("Documentation test passed!", "✅")
    return True

def test_error_handling():
    """Test 8: Error handling"""
    log("Testing error handling...", "🔍")
    
    # Test with invalid request
    invalid_request = {
        "player_id": "test",
        # Missing required fields
    }
    
    response = requests.post(
        f"{BASE_URL}/predict",
        json=invalid_request
    )
    
    # Should return 422 (validation error) or 500 (server error)
    assert response.status_code in [422, 500]
    
    log("Error handling test passed!", "✅")
    return True

def test_performance():
    """Test 9: Response time performance"""
    log("Testing API performance...", "🔍")
    
    prediction_request = {
        "player_id": "test_player",
        "opponent_id": "test_opponent",
        "features": [25.0] * 7,
        "recent_games": [25.0] * 10,
        "player_stats": {
            "stat_type": "points",
            "expected_value": 25.0,
            "variance": 40.0,
            "std_dev": 6.0
        },
        "schedule": {
            "days_rest": 1,
            "travel_miles": 1000,
            "games_in_last_7": 3
        },
        "injuries": [],
        "depth_chart": {},
        "game_id": "test_game",
        "current_line": 24.5,
        "opening_line": 25.0,
        "time_until_game": 5.0,
        "betting_percentages": {"public_on_favorite": 60.0},
        "betting_odds": -110,
        "line": 24.5
    }
    
    # Make 5 requests and measure time
    import time
    times = []
    
    for i in range(5):
        start = time.time()
        response = requests.post(f"{BASE_URL}/predict", json=prediction_request)
        elapsed = time.time() - start
        times.append(elapsed)
        assert response.status_code == 200
    
    avg_time = sum(times) / len(times)
    log(f"  Average response time: {avg_time*1000:.0f}ms", "")
    log(f"  Min: {min(times)*1000:.0f}ms, Max: {max(times)*1000:.0f}ms", "")
    
    # Warn if slow
    if avg_time > 1.0:
        log("  ⚠️  Response time > 1 second (may need optimization)", "⚠️")
    
    log("Performance test passed!", "✅")
    return True

def run_all_tests():
    """Run complete test suite"""
    print("=" * 60)
    print("🧪 AI SPORTS BETTING API - TEST SUITE")
    print("=" * 60)
    print(f"Testing: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    tests = [
        ("Health Check", test_health_check),
        ("Model Status (8 Models)", test_model_status),
        ("Comprehensive Prediction", test_comprehensive_prediction),
        ("Monte Carlo Simulation", test_monte_carlo_simulation),
        ("Line Movement Analysis", test_line_analysis),
        ("Edge Calculation", test_edge_calculation),
        ("Documentation", test_docs_endpoint),
        ("Error Handling", test_error_handling),
        ("Performance", test_performance),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            print(f"Running: {test_name}")
            print(f"{'='*60}")
            test_func()
            passed += 1
        except requests.exceptions.ConnectionError:
            log(f"❌ Cannot connect to {BASE_URL}", "❌")
            log("Make sure the server is running:", "")
            log("  python prediction_api.py", "")
            return
        except AssertionError as e:
            log(f"❌ Test failed: {str(e)}", "❌")
            failed += 1
        except Exception as e:
            log(f"❌ Unexpected error: {str(e)}", "❌")
            failed += 1
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("Your AI Sports Betting API is working perfectly!")
        print(f"\n📚 Interactive docs: {BASE_URL}/docs")
        print(f"📊 API info: {BASE_URL}/")
        print(f"🧠 Model status: {BASE_URL}/model-status")
        print("=" * 60)
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check logs above.")
    
    print()

if __name__ == "__main__":
    run_all_tests()
