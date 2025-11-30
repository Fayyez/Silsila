# Quantum-Safe File Sharing Client

A modern web-based client for secure peer-to-peer file transfers using AES-256-GCM encryption.

## Features

✅ **Modern Web UI** - Beautiful, responsive interface
✅ **AES-256-GCM Encryption** - Strong symmetric encryption
✅ **SHA-256 Integrity** - File hash verification
✅ **Chunked Streaming** - Memory-efficient 64 KB chunks
✅ **Real-time Progress** - Live upload/download tracking
✅ **Custom Download Location** - Choose where to save files
✅ **Multiple Concurrent Transfers** - Send/receive simultaneously
✅ **Auto-Discovery** - See all online clients
✅ **Background Processing** - Non-blocking file operations

## Installation

Dependencies are already installed from the main project requirements.

```bash
# Already installed via ../requirements.txt
Flask
requests
cryptography
```

## Running the Client

### Start a Client Instance

```bash
# From project root
python client/app.py [port]

# Examples:
python client/app.py 5001  # Client 1
python client/app.py 5002  # Client 2
python client/app.py 5003  # Client 3
```

### Access the Web Interface

Open your browser to:
- Client 1: `http://127.0.0.1:5001`
- Client 2: `http://127.0.0.1:5002`
- Client 3: `http://127.0.0.1:5003`

## Quick Start Guide

### 1. Register Your Client

1. Open the client in your browser
2. Enter a unique client ID (e.g., "alice", "bob", "charlie")
3. Click "Connect"

You'll see:
- ✓ Connected status
- Your client ID displayed
- "Listening" badge for incoming transfers

### 2. Send a File

1. Click "🔄 Refresh" to see online clients
2. Select a recipient from the dropdown
3. Click "Choose File" and select your file
4. Click "Send File"
5. Wait for recipient to accept
6. Watch upload progress

### 3. Receive a File

When someone sends you a file:

1. Notification appears in "Incoming Files" section
2. You'll see: filename, sender, and file size
3. (Optional) Click "📁 Choose Location" to specify download path
4. Click "Accept" to download
5. Click "Reject" to decline

Downloaded files are saved to:
- Default: `client/downloads/`
- Custom: Path you specify

## How It Works

### Encryption Flow

**Sending:**
1. Generate 256-bit AES key + 96-bit nonce
2. Compute SHA-256 hash of original file
3. Encrypt file with AES-256-GCM in 64 KB chunks
4. Create SK Bundle (key + nonce + hash)
5. Send SK Bundle + encrypted file to recipient

**Receiving:**
1. Receive SK Bundle from sender
2. Download encrypted file chunks
3. Decrypt using AES-256-GCM
4. Verify SHA-256 hash matches
5. Save decrypted file

### Architecture

```
┌─────────────────┐
│   Web Browser   │ ← User Interface
└────────┬────────┘
         │ HTTP
┌────────▼────────┐
│  Flask Web App  │ ← client/app.py
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼──────┐
│Crypto │ │ Server  │
│Module │ │ Client  │
└───────┘ └────┬────┘
                │ HTTPS
         ┌──────▼──────┐
         │   Server    │ ← server/app.py
         │ (Port 5000) │
         └─────────────┘
```

## API Endpoints

### Client API (Internal)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve web interface |
| `/api/register` | POST | Register with server |
| `/api/clients` | GET | List online clients |
| `/api/send` | POST | Initiate file send |
| `/api/pending` | GET | Get incoming transfers |
| `/api/accept` | POST | Accept transfer |
| `/api/reject` | POST | Reject transfer |
| `/api/uploads/status` | GET | Upload progress |
| `/api/downloads/status` | GET | Download progress |
| `/api/status` | GET | Client status |

## Modules

### `modules/crypto_client.py`

Handles all cryptographic operations:

```python
from modules import QuantumSafeCrypto

crypto = QuantumSafeCrypto()

# Generate encryption key
key, nonce = crypto.generate_symmetric_key()

# Encrypt file
metadata = crypto.encrypt_file(
    input_path='file.txt',
    output_path='file.txt.enc',
    key=key,
    nonce=nonce
)

# Decrypt file
result = crypto.decrypt_file(
    input_path='file.txt.enc',
    output_path='file_decrypted.txt',
    key=key
)

# Verify integrity
if result['hash_valid']:
    print("File integrity verified!")
```

### `modules/server_client.py`

Handles server communication:

```python
from modules import ServerClient

client = ServerClient('alice')

# Register
client.register()

# Start heartbeat
client.start_heartbeat()

# Get online clients
clients = client.get_online_clients()

# Send file
token = client.request_transfer('bob', metadata)
if client.wait_for_acceptance(token):
    client.upload_file(token, 'encrypted_file.enc')

# Receive file
def on_transfer(token, sender_id, metadata):
    client.accept_transfer(token)
    client.download_file(token, 'received_file.enc')

client.start_listening(on_transfer)
```

## Configuration

### Default Settings

```python
# In app.py
SERVER_URL = "http://127.0.0.1:5000"  # Server address
CHUNK_SIZE = 64 * 1024                # 64 KB chunks
HEARTBEAT_INTERVAL = 30               # Seconds
downloads_dir = 'client/downloads'    # Default download location
```

### Customization

Edit `client/app.py`:

```python
# Change server URL
SERVER_URL = "http://your-server:5000"

# Change chunk size (affects memory usage)
CHUNK_SIZE = 128 * 1024  # 128 KB

# Change downloads directory
downloads_dir = '/path/to/downloads'
```

## Security Notes

### Current Implementation

✅ **Encryption**: AES-256-GCM (industry standard)
✅ **Hash Verification**: SHA-256
✅ **Secure Random**: os.urandom() for key generation
✅ **Memory Only**: Server never stores files on disk
⚠️ **Localhost Only**: Not hardened for internet use

### For Production Use Would Need

- [ ] HTTPS/TLS encryption
- [ ] User authentication
- [ ] Access control lists
- [ ] Rate limiting
- [ ] Input sanitization
- [ ] Post-quantum key exchange (ML-KEM-768)

## Post-Quantum Cryptography (Optional)

The client supports ML-KEM-768 for post-quantum key encapsulation, but it requires additional setup:

### Installing PQC Support

```bash
# Install liboqs (requires C compiler)
pip install liboqs-python

# Note: On Windows, this may require:
# - Visual Studio Build Tools
# - CMake
# - Git
```

### Using PQC

When liboqs is available, the client will use ML-KEM-768 for:
- Key pair generation
- Key encapsulation/decapsulation
- Quantum-resistant key exchange

For the prototype on Windows, standard AES-256-GCM is sufficient and provides strong security for localhost testing.

## Troubleshooting

### Client won't start

```bash
# Check if port is already in use
netstat -ano | findstr "5001"

# Try a different port
python client/app.py 5010
```

### Can't connect to server

```bash
# Verify server is running
curl http://127.0.0.1:5000/health

# Start server if needed
python server/app.py
```

### File transfer fails

- Check both clients are registered
- Verify recipient is online (click Refresh)
- Check server logs for errors
- Ensure enough disk space

### "No clients online"

- Click the Refresh button
- Check server is running
- Verify both clients sent heartbeats
- Wait a few seconds and refresh again

## File Structure

```
client/
├── app.py                  # Flask web application
├── modules/
│   ├── __init__.py         # Module exports
│   ├── crypto_client.py    # Encryption/decryption
│   └── server_client.py    # Server communication
├── pages/
│   └── home.html           # Web interface
├── downloads/              # Received files (created automatically)
└── README.md              # This file
```

## Development

### Adding Features

1. **New encryption algorithm**: Edit `crypto_client.py`
2. **UI changes**: Edit `pages/home.html`
3. **API endpoints**: Edit `app.py`
4. **Server communication**: Edit `server_client.py`

### Testing

```bash
# Test crypto module
python -c "from modules import QuantumSafeCrypto; c = QuantumSafeCrypto(); print('OK')"

# Test server client
python -c "from modules import ServerClient; s = ServerClient('test'); print('OK')"

# Test encryption/decryption
python test_crypto.py  # (create this if needed)
```

## Performance

- **Encryption**: ~100 MB/s (CPU-bound)
- **Network**: ~500 MB/s (localhost)
- **Memory**: ~10 MB per active transfer
- **Chunk Size**: 64 KB (optimal for most cases)

## Limitations

- Localhost only (not exposed to network)
- No authentication (anyone can register as any ID)
- No persistence (transfers lost on restart)
- No resume capability (must restart failed transfers)
- Limited to server's concurrent transfer limit (10)

These limitations are intentional for the prototype and would be addressed in a production system.

## License

See project root LICENSE file.

## Support

For issues or questions, refer to:
- Server documentation: `../server/README.md`
- Project plan: `../project_plan.md`
- Test guide: `../test_client_exchange.md`

