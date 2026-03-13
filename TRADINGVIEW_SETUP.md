# TradingView Signal Setup Guide

Bu rehber, TradingView'den botunuza sinyal göndermek için gerekli adımları açıklar.

## 🎯 Genel Bakış

Botunuz zaten TradingView sinyallerini almaya hazır durumda. Webhook endpoint'i: `/webhook/tradingview`

## 📋 Gereksinimler

1. **TradingView Pro/Pro+/Premium** hesabı (webhook özelliği için)
2. **Çalışan bot** (localhost:5000 veya public URL)
3. **Pine Script** stratejisi veya indikatörü

## 🔧 Adım 1: Webhook URL'ini Hazırlayın

### Yerel Test İçin (ngrok ile)
```
https://YOUR-SUBDOMAIN.ngrok-free.app/webhook/tradingview
```

**ngrok Kurulumu:**
1. [ngrok.com](https://ngrok.com) hesabı oluşturun
2. ngrok'u indirin ve kurun
3. Auth token ayarlayın: `ngrok config add-authtoken YOUR_TOKEN`
4. Bot'u çalıştırın: `python run.py`
5. ngrok'u başlatın: `ngrok http 5000` veya `python start_ngrok.py`

**Detaylı ngrok rehberi:** `NGROK_SETUP.md` dosyasına bakın

### Production İçin (Public URL)
Botunuzu production'da çalıştırmak için:
- **VPS/Cloud** sunucuya deploy (önerilen)
- **ngrok Pro** hesabı (sabit domain için)
- **Port forwarding** ile router ayarları

## 🎨 Adım 2: Pine Script Kodu

TradingView'de kullanabileceğiniz örnek Pine Script kodu:

```pinescript
//@version=5
strategy("Trading Bot Signal", overlay=true)

// Parametreler
rsi_length = input.int(14, "RSI Length")
rsi_overbought = input.int(70, "RSI Overbought")
rsi_oversold = input.int(30, "RSI Oversold")

// İndikatörler
rsi = ta.rsi(close, rsi_length)

// Sinyal koşulları
long_condition = ta.crossover(rsi, rsi_oversold)
short_condition = ta.crossunder(rsi, rsi_overbought)

// Long pozisyon
if long_condition
    strategy.entry("Long", strategy.long)
    // Webhook mesajı
    alert('{"action": "buy", "symbol": "{{ticker}}", "price": {{close}}, "timestamp": "{{time}}", "strategy": "RSI_Strategy"}', alert.freq_once_per_bar)

// Short pozisyon  
if short_condition
    strategy.entry("Short", strategy.short)
    // Webhook mesajı
    alert('{"action": "sell", "symbol": "{{ticker}}", "price": {{close}}, "timestamp": "{{time}}", "strategy": "RSI_Strategy"}', alert.freq_once_per_bar)

// Çıkış koşulları
if strategy.position_size > 0 and ta.crossunder(rsi, rsi_overbought)
    strategy.close("Long")
    alert('{"action": "close", "symbol": "{{ticker}}", "price": {{close}}, "timestamp": "{{time}}", "strategy": "RSI_Strategy"}', alert.freq_once_per_bar)

if strategy.position_size < 0 and ta.crossover(rsi, rsi_oversold)
    strategy.close("Short")
    alert('{"action": "close", "symbol": "{{ticker}}", "price": {{close}}, "timestamp": "{{time}}", "strategy": "RSI_Strategy"}', alert.freq_once_per_bar)
```

## 🚨 Adım 3: Alert (Uyarı) Kurulumu

1. **Pine Script'i grafike ekleyin**
2. **Sağ tıklayın** → "Add Alert"
3. **Condition**: Script adınızı seçin
4. **Webhook URL**: Botunuzun webhook URL'ini girin
5. **Message**: Aşağıdaki JSON formatını kullanın

### Örnek Webhook Mesajları

#### Buy Signal
```json
{
    "action": "buy",
    "symbol": "{{ticker}}",
    "price": {{close}},
    "timestamp": "{{time}}",
    "strategy": "My_Strategy",
    "timeframe": "{{interval}}",
    "volume": {{volume}}
}
```

#### Sell Signal
```json
{
    "action": "sell", 
    "symbol": "{{ticker}}",
    "price": {{close}},
    "timestamp": "{{time}}",
    "strategy": "My_Strategy",
    "timeframe": "{{interval}}",
    "volume": {{volume}}
}
```

#### Close Position
```json
{
    "action": "close",
    "symbol": "{{ticker}}",
    "price": {{close}},
    "timestamp": "{{time}}",
    "strategy": "My_Strategy"
}
```

## 📊 Desteklenen Sinyal Formatları

Bot aşağıdaki action türlerini destekler:

- `"buy"` - Long pozisyon aç
- `"sell"` - Short pozisyon aç  
- `"close"` - Mevcut pozisyonu kapat
- `"close_long"` - Sadece long pozisyonu kapat
- `"close_short"` - Sadece short pozisyonu kapat

## 🔍 Adım 4: Test Etme

### 1. Manuel Test
```bash
curl -X POST http://localhost:5000/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{
    "action": "buy",
    "symbol": "BTCUSDT",
    "price": 45000,
    "timestamp": "2024-01-01T12:00:00Z",
    "strategy": "Test_Strategy"
  }'
```

### 2. TradingView Test
- Alert oluşturduktan sonra "Test" butonuna tıklayın
- Bot loglarını kontrol edin
- Telegram'dan bildirim gelip gelmediğini kontrol edin

## ⚙️ Adım 5: Bot Ayarları

Web panelinden (`http://localhost:5000/settings`) aşağıdaki ayarları yapın:

### Binance API
- API Key ve Secret Key'i girin
- Testnet modunu aktif edin (test için)

### Risk Yönetimi
- Maksimum pozisyon boyutu
- Stop loss yüzdesi
- Günlük kayıp limiti

### Telegram
- Bot token'ı girin
- Chat ID'yi otomatik çekin

### Take Profit Sistemi
- TP1, TP2, TP3 seviyelerini ayarlayın
- Trailing TP'yi aktif edin

## 🛡️ Güvenlik Önerileri

1. **Webhook URL'ini gizli tutun**
2. **IP whitelist** kullanın (production'da)
3. **Rate limiting** aktif tutun
4. **Testnet'te test edin** önce
5. **Küçük pozisyonlarla başlayın**

## 🔧 Sorun Giderme

### Sinyal Gelmiyor
- Webhook URL'ini kontrol edin
- TradingView Pro hesabınız var mı?
- Alert doğru kurulmuş mu?
- Bot çalışıyor mu?

### İşlem Yapılmıyor
- Binance API ayarları doğru mu?
- Yeterli bakiye var mı?
- Risk limitleri aşılmış mı?
- Symbol formatı doğru mu? (BTCUSDT)

### Telegram Bildirimi Gelmiyor
- Bot token doğru mu?
- Chat ID doğru mu?
- Telegram bildirimleri aktif mi?

## 📝 Örnek Strateji Fikirleri

### 1. RSI Stratejisi
- RSI < 30: Buy
- RSI > 70: Sell

### 2. Moving Average Cross
- MA50 > MA200: Buy
- MA50 < MA200: Sell

### 3. Bollinger Bands
- Fiyat alt banda değerse: Buy
- Fiyat üst banda değerse: Sell

### 4. MACD Stratejisi
- MACD > Signal: Buy
- MACD < Signal: Sell

## 🚀 İleri Seviye Özellikler

### Çoklu Timeframe
```json
{
    "action": "buy",
    "symbol": "BTCUSDT", 
    "timeframes": ["1h", "4h", "1d"],
    "confirmation": "all"
}
```

### Koşullu İşlemler
```json
{
    "action": "buy",
    "symbol": "BTCUSDT",
    "conditions": {
        "rsi": {"value": 25, "operator": "<"},
        "volume": {"value": 1000000, "operator": ">"}
    }
}
```

### Dinamik Position Size
```json
{
    "action": "buy",
    "symbol": "BTCUSDT",
    "position_size_percent": 2.5,
    "risk_reward_ratio": 3
}
```

## 📞 Destek

Sorunlarınız için:
1. Bot loglarını kontrol edin
2. Web panelindeki "Signals" sayfasından gelen sinyalleri görün
3. "Trades" sayfasından işlem geçmişini kontrol edin

---

**⚠️ Önemli Uyarı**: Gerçek para ile işlem yapmadan önce mutlaka testnet'te test edin!