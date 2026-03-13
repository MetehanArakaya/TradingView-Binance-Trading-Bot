# TradingView-Binance Trading Bot

A sophisticated automated trading bot that receives signals from TradingView webhooks and executes trades on Binance Futures with 10x leverage. Features include risk management, Telegram notifications, and a web management panel.

## 🚀 Features

### Core Trading Features
- **TradingView Integration**: Receives webhook signals from TradingView alerts
- **Binance Futures Trading**: Automated trading with 10x leverage
- **Signal Processing**: Validates and processes BUY, SELL, and CLOSE signals
- **Position Management**: Tracks open positions and manages risk

### Risk Management
- **Flexible Position Sizing**: Percentage-based or fixed USDT amounts
- **Stop Loss & Take Profit**: Automatic risk management orders
- **Trailing Stop**: Dynamic stop loss adjustment
- **Daily Loss Limits**: Maximum daily loss protection
- **Position Limits**: Maximum concurrent positions control
- **Symbol Filtering**: Whitelist/blacklist trading pairs

### Security & Safety
- **Emergency Stop**: Instant halt of all trading activities
- **API Key Encryption**: Secure storage of sensitive credentials
- **Webhook Signature Verification**: Validates incoming signals
- **IP Whitelisting**: Restricts webhook access
- **Rate Limiting**: Prevents API abuse

### Notifications & Monitoring
- **Telegram Integration**: Real-time trade notifications
- **Web Dashboard**: Monitor positions, trades, and performance
- **Comprehensive Logging**: Detailed system and trade logs
- **Performance Analytics**: Track P&L and trading statistics

## 📁 Project Structure

```
trading-bot/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── models/                  # Database models
│   │   ├── __init__.py
│   │   ├── trade.py            # Trade records
│   │   ├── signal.py           # TradingView signals
│   │   ├── position.py         # Position tracking
│   │   └── settings.py         # Bot configuration
│   ├── api/                     # Binance API integration
│   │   ├── __init__.py
│   │   ├── binance_client.py   # Binance API wrapper
│   │   └── trading_engine.py   # Trade execution logic
│   ├── webhook/                 # TradingView webhook handler
│   │   ├── __init__.py
│   │   └── routes.py           # Webhook endpoints
│   ├── web/                     # Web management panel
│   │   ├── __init__.py
│   │   └── routes.py           # Web interface
│   ├── telegram/                # Telegram bot integration
│   │   └── __init__.py
│   ├── risk/                    # Risk management
│   │   └── __init__.py
│   └── utils/                   # Utility functions
│       └── __init__.py
├── config/
│   └── settings.py             # Configuration management
├── templates/                   # HTML templates (to be added)
├── static/                      # Static files (to be added)
├── tests/                       # Test files (to be added)
├── requirements.txt             # Python dependencies
├── run.py                      # Application entry point
├── .env.example                # Environment variables template
└── README.md                   # This file
```

## 🛠️ Installation

### Prerequisites
- Python 3.9 or higher
- Binance Futures account with API access
- TradingView account (Pro+ for webhooks)
- Telegram bot token (optional)

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd trading-bot
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   flask --app run.py init-db
   ```

6. **Run the application**
   ```bash
   python run.py
   ```

## ⚙️ Configuration

### Environment Variables (.env)

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Database
DATABASE_URL=sqlite:///trading_bot.db

# Binance API Configuration
BINANCE_API_KEY=your-binance-api-key
BINANCE_SECRET_KEY=your-binance-secret-key
BINANCE_TESTNET=True

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id

# TradingView Webhook Security
WEBHOOK_SECRET=your-webhook-secret-key

# Security
ENCRYPTION_KEY=your-encryption-key-here
ALLOWED_IPS=127.0.0.1,::1
```

### TradingView Webhook Setup

1. Create a TradingView alert
2. Set webhook URL: `https://your-domain.com/webhook/tradingview`
3. Use JSON format for the message:

```json
{
    "symbol": "{{ticker}}",
    "action": "buy",
    "price": {{close}},
    "stop_loss": {{close}} * 0.97,
    "take_profit": {{close}} * 1.06
}
```

### Supported Signal Actions
- `buy` or `long`: Open long position
- `sell` or `short`: Open short position  
- `close` or `exit`: Close existing position

## 🔧 API Endpoints

### Webhook Endpoints
- `POST /webhook/tradingview` - Receive TradingView signals
- `POST /webhook/test` - Test webhook (debug mode only)
- `GET /webhook/status` - Webhook status

### Web Interface
- `GET /` - Dashboard
- `GET /settings` - Bot configuration
- `GET /trades` - Trade history
- `GET /positions` - Active positions
- `GET /api/status` - Bot status API

## 📊 Database Schema

### Tables
- **signals**: TradingView webhook signals
- **trades**: Individual trade records
- **positions**: Active position tracking
- **bot_settings**: Bot configuration and settings

## 🔒 Security Features

### API Key Protection
- All sensitive credentials are encrypted using Fernet encryption
- Environment variables for additional security layer
- Separate testnet/mainnet configurations

### Webhook Security
- HMAC signature verification
- IP address whitelisting
- Rate limiting protection

### Trading Safety
- Emergency stop mechanism
- Position size limits
- Daily loss limits
- Symbol filtering

## 📈 Risk Management

### Position Sizing
- **Percentage Method**: Risk a percentage of total portfolio
- **Fixed Amount**: Use fixed USDT amount per trade

### Stop Loss & Take Profit
- Automatic placement based on signal data
- Configurable default percentages
- Trailing stop functionality

### Limits & Controls
- Maximum concurrent positions
- Daily loss limits (percentage or fixed amount)
- Symbol whitelist/blacklist
- Trading hours restrictions

## 🤖 Telegram Integration

### Notification Types
- Trade opening/closing alerts
- Error notifications
- Daily performance summaries
- Emergency stop alerts

### Setup
1. Create a Telegram bot via @BotFather
2. Get your chat ID
3. Configure in bot settings

## 🚨 Emergency Procedures

### Emergency Stop
- Immediately stops all trading
- Closes all open positions
- Prevents new signal processing
- Can be triggered via web interface or API

### Recovery
1. Check system logs for issues
2. Verify API connectivity
3. Review position status
4. Disable emergency stop when ready

## 📝 Logging

### Log Levels
- **INFO**: Normal operations, trade executions
- **WARNING**: Non-critical issues, rejected signals
- **ERROR**: Critical errors, failed trades
- **DEBUG**: Detailed debugging information

### Log Files
- `logs/trading_bot.log` - Main application log
- Automatic log rotation (10MB max, 10 backups)

## 🧪 Testing

### Test Webhook
```bash
curl -X POST http://localhost:5000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","action":"buy","price":45000}'
```

### Database Commands
```bash
# Initialize database
flask --app run.py init-db

# Reset database (WARNING: Deletes all data)
flask --app run.py reset-db

# Create sample data
flask --app run.py create-sample-data
```

## ⚠️ Important Notes

### Testnet vs Mainnet
- **Always start with testnet** for testing
- Testnet uses fake money for safe testing
- Switch to mainnet only after thorough testing

### Risk Disclaimer
- **Trading involves significant risk**
- **Never risk more than you can afford to lose**
- **Test thoroughly before live trading**
- **Monitor positions regularly**

### API Rate Limits
- Binance has strict rate limits
- Bot includes rate limiting protection
- Monitor API usage in production

## 🔄 Development Status

### ✅ Completed Features
- [x] Project structure and configuration
- [x] Database models and migrations
- [x] TradingView webhook integration
- [x] Signal validation and parsing
- [x] Binance API client
- [x] Trading engine with 10x leverage
- [x] Basic web interface structure

### 🚧 In Progress
- [ ] Risk management system
- [ ] Telegram notifications
- [ ] Web dashboard UI
- [ ] Position monitoring
- [ ] Emergency stop mechanism

### 📋 Planned Features
- [ ] Advanced analytics
- [ ] Backtesting capabilities
- [ ] Multiple exchange support
- [ ] Mobile app
- [ ] Advanced order types

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves substantial risk and may result in significant financial losses. The authors are not responsible for any financial losses incurred through the use of this software. Always conduct thorough testing and risk assessment before using any automated trading system.