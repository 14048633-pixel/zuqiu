# Football Prediction System - Complete Documentation

## Overview

A comprehensive football prediction system using machine learning, deep learning, and free API integrations.

## System Architecture

```
football-prediction-system/
├── Data Layer
│   ├── Free APIs
│   │   ├── InferSports (odds, fair probability)
│   │   ├── SportScore (live scores)
│   │   └── API-Football (fixtures, stats)
│   └── xG Data
│       └── Understat (expected goals)
├── Model Layer
│   ├── XGBoost (63.19% - Best)
│   ├── LSTM (60.68%)
│   ├── Transformer (61.11%)
│   └── Ensemble (55.48%)
├── Feature Layer
│   ├── xG Features (18 features)
│   ├── Shot Features
│   ├── Form Features
│   └── Head-to-Head Features
└── Output Layer
    ├── Predictions
    ├── Monitoring Dashboard
    └── Value Detection
```

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install pandas numpy scikit-learn xgboost torch requests joblib

# Clone/download the system
cd football-prediction-system
```

### 2. Run the System

```bash
# Run final system
python final_system.py

# Get live matches
python unified_api.py --matches

# Test free APIs
python free_apis.py --test

# Model comparison
python model_comparison.py
```

## File Structure

| File | Description | Usage |
|------|-------------|-------|
| `final_system.py` | Complete system | `python final_system.py` |
| `unified_api.py` | Unified API interface | `python unified_api.py --matches` |
| `free_apis.py` | Free API integration | `python free_apis.py --test` |
| `lstm_model.py` | LSTM model | `python lstm_model.py --train` |
| `transformer_model.py` | Transformer model | `python transformer_model.py --train` |
| `model_comparison.py` | Model comparison | `python model_comparison.py` |
| `monitoring.py` | Real-time monitoring | `python monitoring.py --dashboard` |
| `player_data.py` | Player data | `python player_data.py --team "Man City"` |
| `production.py` | Production predictions | `python production.py --predict` |
| `combined_system.py` | Combined predictions | `python combined_system.py --today` |

## Free APIs

### 1. InferSports (Recommended)

- **Data**: Odds, fair probability, sharp lines
- **Limit**: Free tier available
- **Setup**: No API key needed for basic use

```bash
# Get today's matches
bash scripts/today.sh --sport football

# Get fair odds
bash scripts/fair.sh "Man City vs Arsenal"
```

### 2. SportScore

- **Data**: Live scores, fixtures, stats
- **Limit**: No restrictions
- **Setup**: No API key needed

```python
from free_apis import SportScoreAPI

api = SportScoreAPI()
matches = api.get_matches()
```

### 3. API-Football

- **Data**: Fixtures, live scores, team stats
- **Limit**: 100 requests/day free
- **Setup**: Register at api-football.com

```python
from free_apis import APIFootball

api = APIFootball(api_key="YOUR_KEY")
fixtures = api.get_fixtures(league=39, date="2026-07-27")
```

## Models

### XGBoost (Best Performance)

- **Accuracy**: 63.19%
- **Training Time**: ~10 seconds
- **Features**: 35 features

```python
# Train model
python advanced_fast.py

# Predict
python production.py --predict
```

### LSTM

- **Accuracy**: 60.68%
- **Training Time**: ~5 minutes
- **Architecture**: 2-layer LSTM

```python
# Train
python lstm_model.py --train

# Predict
python lstm_model.py --predict
```

### Transformer

- **Accuracy**: 61.11%
- **Training Time**: ~3 minutes
- **Architecture**: 2-layer Transformer

```python
# Train
python transformer_model.py --train

# Predict
python transformer_model.py --predict
```

## Features

### xG Features

- `home_xG` - Home team expected goals
- `home_xGA` - Home team expected goals against
- `home_xGD` - Home team expected goal difference
- `away_xG` - Away team expected goals
- `away_xGA` - Away team expected goals against
- `away_xGD` - Away team expected goal difference
- `xG_diff` - Expected goal difference

### Shot Features

- `home_shots` - Home team shots
- `home_shots_on_target` - Home team shots on target
- `away_shots` - Away team shots
- `away_shots_on_target` - Away team shots on target
- `shots_diff` - Shot difference
- `shots_on_target_diff` - Shots on target difference

### Attack/Defense Features

- `home_attack` - Home attack strength
- `home_defense` - Home defense strength
- `away_attack` - Away attack strength
- `away_defense` - Away defense strength
- `attack_diff` - Attack difference
- `defense_diff` - Defense difference

## Usage Examples

### 1. Predict a Match

```python
from final_system import FinalSystem

system = FinalSystem()
system.load_all()

pred = system.predict_match("Man City", "Arsenal")
print(f"Prediction: {pred['prediction']}")
print(f"Confidence: {pred['confidence']:.1%}")
```

### 2. Get Live Matches

```python
from unified_api import UnifiedAPI

api = UnifiedAPI()
matches = api.get_all_matches()

for match in matches:
    print(f"{match['home']} vs {match['away']}")
```

### 3. Monitor Predictions

```python
from monitoring import MonitoringSystem

monitor = MonitoringSystem()
monitor.log_prediction("2026-07-27", "Man City", "Arsenal", "Home", 0.6, "H")
monitor.display_dashboard()
```

### 4. Get Player Data

```python
from player_data import PlayerDataSystem

system = PlayerDataSystem()
injuries = system.get_injuries("Man City")
print(f"Injuries: {len(injuries)}")
```

## Model Comparison

| Model | Accuracy | Training Time | Parameters |
|-------|----------|---------------|------------|
| XGBoost | 63.19% | ~10s | 100 trees |
| Transformer | 61.11% | ~3min | ~70K |
| LSTM | 60.68% | ~5min | ~216K |
| Ensemble | 55.48% | - | Combined |

## API Endpoints

### InferSports

```bash
# Today's matches
GET /v1/matches

# Fair odds
GET /v1/fair/{team_query}

# Sharp line
GET /v1/line/{team_query}
```

### SportScore

```bash
# Matches
GET /v1/football/matches

# Standings
GET /v1/leagues/{league_id}/standings
```

### API-Football

```bash
# Fixtures
GET /fixtures?league=39&date=2026-07-27

# Live scores
GET /fixtures?live=all

# Team statistics
GET /teams/statistics?league=39&season=2025&team=50
```

## Configuration

### API Keys

```python
# Set in free_apis.py
API_FOOTBALL_KEY = "your_key_here"  # Optional, 100/day free
```

### Model Parameters

```python
# XGBoost parameters (in advanced_fast.py)
params = {
    'n_estimators': 300,
    'max_depth': 5,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8
}
```

## Troubleshooting

### Common Issues

1. **Import Error**
   ```bash
   pip install pandas numpy scikit-learn xgboost torch
   ```

2. **API Connection Error**
   ```python
   # Check internet connection
   # Try mock data
   api = SportScoreAPI()
   matches = api.get_mock_matches()
   ```

3. **Model Not Found**
   ```bash
   # Train models first
   python advanced_fast.py
   python lstm_model.py --train
   python transformer_model.py --train
   ```

## Performance Tips

1. **Use XGBoost** for fastest predictions
2. **Cache API responses** to reduce calls
3. **Use batch predictions** for multiple matches
4. **Update xG data** weekly for best results

## License

This system is for educational purposes only. Use responsibly.

## Support

For issues or questions, check the code comments or create an issue.
