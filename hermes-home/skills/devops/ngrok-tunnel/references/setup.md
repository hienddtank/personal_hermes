# Ngrok Setup & Authentication

## Installation

### Python SDK (recommended for programmatic use)
```bash
pip install pyngrok
```

### CLI
```bash
# Download: https://ngrok.com/download
# Linux:
wget https://bin.equinox.com/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# Windows (via winget):
winget install Ngrok.Ngrok

# macOS:
brew install ngrok/ngrok/ngrok
```

### Authentication
```bash
ngrok authtoken YOUR_TOKEN_HERE
# Token from: https://dashboard.ngrok.com/user/settings
```

### Docker Container Environment
Inside the Hermes container, ngrok API runs on localhost:4040:
```python
from pyngrok import ngrok
tunnel = ngrok.connect(8765, "http")
# Access via: http://localhost:4040/api/tunnels
```

## Verification
```bash
ngrok version          # Check installation
ngrok authtoken        # Should show your token (masked)
ngrok config add-config  # List config locations
```
