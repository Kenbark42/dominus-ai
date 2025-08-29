# Dominus AI Deployment Guide

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Kenbark42/dominus-ai.git
cd dominus-ai

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start services
./scripts/start-services.sh
```

## Systemd Service Installation

### Install the service
```bash
sudo cp dominus-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dominus-ai.service
sudo systemctl start dominus-ai.service
```

### Check service status
```bash
sudo systemctl status dominus-ai.service
```

### View logs
```bash
journalctl -u dominus-ai.service -f
```

## Manual Start

If you prefer to run without systemd:

```bash
cd ~/ai/dominus-ai/services
python3 ollama-bridge-v2.py
```

## Nginx Configuration

To expose the service via HTTPS, add this to your nginx configuration:

```nginx
server {
    listen 8001 ssl;
    server_name api.darkfoo.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Long timeout for LLM responses
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
```

## Testing

### Health Check
```bash
curl http://localhost:8090/health
```

### Generate Text
```bash
curl -X POST http://localhost:8090/generate \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": "Hello, world!",
    "parameters": {
      "max_new_tokens": 100
    }
  }'
```

## Troubleshooting

### Service won't start
- Check Ollama is running: `systemctl status ollama`
- Check port 8090 is free: `lsof -i :8090`
- Check logs: `tail -f ~/ai/dominus-ai/logs/bridge.log`

### Model not found
- Pull the model: `ollama pull gpt-oss:120b`
- List models: `ollama list`

### Connection refused
- Check firewall: `sudo ufw status`
- Verify service is listening: `ss -tuln | grep 8090`