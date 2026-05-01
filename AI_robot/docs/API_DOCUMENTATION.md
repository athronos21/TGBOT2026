# API Documentation

## Overview

This document describes the REST API for the Multi-Robot Trading System.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

All API endpoints require authentication using a Bearer token.

### Get API Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Use Token

Include the token in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Endpoints

### System Status

#### Get System Status

```
GET /status
```

**Response:**
```json
{
  "status": "running",
  "uptime": "2 days, 3 hours, 15 minutes",
  "robots_active": 10,
  "robots_total": 10,
  "database": {
    "postgresql": "connected",
    "mongodb": "connected",
    "redis": "connected"
  },
  "mt5": "connected",
  "telegram": "connected"
}
```

### Account Information

#### Get Account Info

```
GET /account
```

**Response:**
```json
{
  "balance": 1250.00,
  "equity": 1245.50,
  "margin": 125.00,
  "free_margin": 1120.50,
  "margin_level": 1000.00,
  "currency": "USD",
  "leverage": 500
}
```

### Trades

#### Get Open Trades

```
GET /trades/open
```

**Response:**
```json
{
  "trades": [
    {
      "id": 1234,
      "symbol": "XAUUSD",
      "type": "buy",
      "volume": 0.10,
      "open_price": 1945.00,
      "current_price": 1950.25,
      "profit": 52.50,
      "sl": 1940.00,
      "tp": 1960.00,
      "open_time": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "total_profit": 52.50
}
```

#### Get Trade History

```
GET /trades/history?start=2024-01-01&end=2024-12-31
```

**Response:**
```json
{
  "trades": [
    {
      "id": 1234,
      "symbol": "XAUUSD",
      "type": "buy",
      "volume": 0.10,
      "open_price": 1945.00,
      "close_price": 1950.25,
      "profit": 52.50,
      "open_time": "2024-01-15T10:30:00Z",
      "close_time": "2024-01-15T12:45:00Z"
    }
  ],
  "total": 156,
  "total_profit": 245.50
}
```

### Performance

#### Get Performance Metrics

```
GET /performance
```

**Response:**
```json
{
  "total_trades": 156,
  "win_rate": 58.33,
  "profit_factor": 1.45,
  "total_profit": 245.50,
  "max_drawdown": 6.2,
  "sharpe_ratio": 1.85,
  "profit_loss_ratio": 1.65,
  "daily": {
    "profit": 12.30,
    "trades": 5
  },
  "weekly": {
    "profit": 45.60,
    "trades": 22
  },
  "monthly": {
    "profit": 125.80,
    "trades": 89
  }
}
```

### Control

#### Pause Trading

```
POST /control/pause
```

**Response:**
```json
{
  "status": "paused",
  "message": "Trading has been paused"
}
```

#### Resume Trading

```
POST /control/resume
```

**Response:**
```json
{
  "status": "running",
  "message": "Trading has been resumed"
}
```

#### Emergency Stop

```
POST /control/killswitch
```

**Response:**
```json
{
  "status": "stopped",
  "message": "Emergency stop activated. All positions closed.",
  "positions_closed": 3
}
```

### Configuration

#### Get Configuration

```
GET /config
```

**Response:**
```json
{
  "trading": {
    "style": "day_trading",
    "risk_profile": "moderate"
  },
  "risk": {
    "profile": "moderate",
    "risk_per_trade": 1.0,
    "max_daily_loss": 3.0,
    "max_drawdown": 10.0
  },
  "robots": {
    "enabled": ["price_bot", "structure_bot", "liquidity_bot"]
  }
}
```

#### Update Configuration

```
PUT /config
Content-Type: application/json

{
  "trading": {
    "risk_profile": "conservative"
  }
}
```

**Response:**
```json
{
  "status": "updated",
  "message": "Configuration updated successfully"
}
```

### Market Data

#### Get Current Price

```
GET /market/XAUUSD/price
```

**Response:**
```json
{
  "symbol": "XAUUSD",
  "bid": 1950.25,
  "ask": 1950.50,
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### Get OHLC Data

```
GET /market/XAUUSD/candles?timeframe=H1&limit=100
```

**Response:**
```json
{
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "candles": [
    {
      "timestamp": "2024-01-15T13:00:00Z",
      "open": 1948.50,
      "high": 1951.00,
      "low": 1948.00,
      "close": 1950.25
    }
  ]
}
```

## Error Responses

### 400 Bad Request

```json
{
  "error": "invalid_request",
  "message": "Invalid request parameters"
}
```

### 401 Unauthorized

```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

### 403 Forbidden

```json
{
  "error": "forbidden",
  "message": "You do not have permission to access this resource"
}
```

### 404 Not Found

```json
{
  "error": "not_found",
  "message": "Resource not found"
}
```

### 500 Internal Server Error

```json
{
  "error": "internal_error",
  "message": "An internal error occurred"
}
```

## WebSocket API

### Connection

```
ws://localhost:8000/ws
```

### Subscribe to Events

```json
{
  "action": "subscribe",
  "events": ["trade_update", "status_update", "performance_update"]
}
```

### Event Types

#### Trade Update

```json
{
  "type": "trade_update",
  "data": {
    "id": 1234,
    "symbol": "XAUUSD",
    "type": "buy",
    "profit": 52.50,
    "equity": 1245.50
  }
}
```

#### Status Update

```json
{
  "type": "status_update",
  "data": {
    "status": "running",
    "robots_active": 10,
    "open_positions": 3
  }
}
```

#### Performance Update

```json
{
  "type": "performance_update",
  "data": {
    "win_rate": 58.33,
    "total_profit": 245.50,
    "profit_factor": 1.45
  }
}
```

## Rate Limiting

- 100 requests per minute
- 1000 requests per hour
- 10000 requests per day

## Examples

### Python Example

```python
import requests

# Login
response = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    json={'username': 'admin', 'password': 'your_password'}
)
token = response.json()['access_token']

# Get status
headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8000/api/v1/status', headers=headers)
print(response.json())

# Get account info
response = requests.get('http://localhost:8000/api/v1/account', headers=headers)
print(response.json())
```

### JavaScript Example

```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'admin', password: 'your_password'})
});
const {access_token} = await loginResponse.json();

// Get status
const statusResponse = await fetch('http://localhost:8000/api/v1/status', {
  headers: {'Authorization': `Bearer ${access_token}`}
});
const status = await statusResponse.json();
console.log(status);
```

### cURL Example

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'

# Get status
curl -X GET http://localhost:8000/api/v1/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Security

- All endpoints require authentication
- Use HTTPS in production
- Store tokens securely
- Implement rate limiting
- Validate all inputs

## Support

For API issues:
1. Check this documentation
2. Review error messages
3. Test with curl first
4. Contact support if needed
