# MetaTrader 5 Setup Guide for Linux

## Overview
MetaTrader 5 is a Windows application, but it can be run on Linux using Wine. This guide provides instructions for setting up MT5 on Linux for the Multi-Robot Trading System.

## Prerequisites
- Ubuntu 22.04+ or compatible Linux distribution
- Wine installed (for running Windows applications)
- Active internet connection
- MT5 broker account (demo or live)

## Installation Options

### Option 1: Using Wine (Recommended for Development)

1. **Install Wine**
```bash
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get install -y wine64 wine32 winetricks
```

2. **Download MetaTrader 5**
```bash
cd ~/Downloads
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
```

3. **Install MT5 using Wine**
```bash
wine mt5setup.exe
```

4. **Configure MT5**
- Follow the installation wizard
- Select your broker from the list
- Enter your account credentials
- Enable "Allow algorithmic trading" in Tools → Options → Expert Advisors
- Enable "Allow DLL imports" in the same section

### Option 2: Using Windows VPS (Recommended for Production)

For production trading, it's recommended to use a Windows VPS:

1. **Rent a Windows VPS**
   - Providers: Vultr, DigitalOcean, AWS, Azure
   - Minimum specs: 2 CPU cores, 4GB RAM, 50GB SSD
   - Location: Close to your broker's server for low latency

2. **Install MT5 on Windows VPS**
   - Download MT5 from your broker's website
   - Install and configure with your account
   - Enable algorithmic trading

3. **Connect from Linux**
   - Use Python's MetaTrader5 package to connect remotely
   - Or run the trading system on the Windows VPS

### Option 3: Python-Only Approach (No MT5 GUI)

For headless operation, you can use the MetaTrader5 Python package:

```bash
# Install the MetaTrader5 Python package
pip install MetaTrader5
```

**Note:** This still requires MT5 terminal to be installed and running (can be on a remote Windows machine).

## Python Integration

### Install MetaTrader5 Python Package

```bash
cd AI_robot
source venv/bin/activate
pip install MetaTrader5
```

### Test Connection

Create a test script to verify MT5 connection:

```python
import MetaTrader5 as mt5

# Initialize MT5 connection
if not mt5.initialize():
    print("MT5 initialization failed")
    print(mt5.last_error())
    quit()

# Get account info
account_info = mt5.account_info()
if account_info is not None:
    print(f"Account balance: {account_info.balance}")
    print(f"Account leverage: {account_info.leverage}")
    print("MT5 connection successful!")
else:
    print("Failed to get account info")
    print(mt5.last_error())

# Shutdown MT5 connection
mt5.shutdown()
```

## Broker Setup

### Recommended Brokers for Algorithmic Trading

1. **IC Markets**
   - Low spreads
   - Good API support
   - Minimum deposit: $200 (but can start with demo)

2. **Pepperstone**
   - Excellent execution speed
   - MetaTrader 5 support
   - Demo accounts available

3. **XM**
   - Micro accounts available
   - Good for small capital ($10+)
   - Demo accounts available

### Demo Account Setup

1. Open MT5 terminal
2. File → Open an Account
3. Select your broker
4. Choose "Demo Account"
5. Fill in the registration form
6. Save your login credentials

## Configuration for Trading System

After MT5 is installed and configured, update the system configuration:

```yaml
# config.yaml
mt5:
  broker: "IC Markets"  # Your broker name
  account_type: "demo"  # demo or live
  account_number: 12345678  # Your account number
  server: "ICMarketsSC-Demo"  # Your broker's server
  password: "${MT5_PASSWORD}"  # Store in .env file
  leverage: 500
  path: "/path/to/mt5/terminal.exe"  # For Wine: ~/.wine/drive_c/Program Files/MetaTrader 5/terminal64.exe
```

## Troubleshooting

### MT5 Won't Start with Wine
- Install required Wine dependencies: `winetricks vcrun2015 dotnet48`
- Check Wine version: `wine --version` (should be 6.0+)
- Try running in a clean Wine prefix

### Python Can't Connect to MT5
- Ensure MT5 terminal is running
- Check that "Allow algorithmic trading" is enabled
- Verify account credentials are correct
- Check firewall settings

### Connection Timeout
- Ensure stable internet connection
- Check broker server status
- Try different broker server if available

## Next Steps

1. Install MT5 using one of the options above
2. Create a demo account with your chosen broker
3. Test the Python connection
4. Update the system configuration with your MT5 details
5. Proceed to the next task in the implementation plan

## Security Notes

- Never commit MT5 passwords to git
- Store credentials in `.env` file
- Use environment variables for sensitive data
- Enable 2FA on your broker account if available
- Use demo account for testing before going live

## Resources

- [MetaTrader 5 Official Website](https://www.metatrader5.com/)
- [MetaTrader5 Python Documentation](https://www.mql5.com/en/docs/python_metatrader5)
- [Wine Documentation](https://www.winehq.org/documentation)
