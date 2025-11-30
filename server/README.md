# Quantum-Safe File Sharing Server

This is the server component of the Quantum-Safe File Sharing Service. It provides signaling, client registry, and in-memory streaming capabilities for secure peer-to-peer file transfers.

## Features

- ✅ **Client Registration & Discovery**: Track online clients and their availability
- ✅ **Heartbeat Mechanism**: Automatic client timeout after 5 minutes of inactivity
- ✅ **Transfer Signaling**: Request/Accept/Reject handshake protocol
- ✅ **In-Memory Streaming**: Zero-disk-storage data conduits (64KB chunks)
- ✅ **Concurrent Transfers**: Support up to 10 simultaneous file transfers
- ✅ **Thread-Safe**: Full threading support for concurrent operations
- ✅ **Long-Polling**: Efficient notification system for incoming transfers

## Architecture

### Modules

1. **`registry.py`** - Client management and active user tracking
2. **`signaling.py`** - Transfer request handling and long-polling
3. **`streaming.py`** - In-memory producer-consumer streaming conduits

### Key Design Decisions

- **No Disk Storage**: Files are never written to disk on the server
- **In-Memory Buffers**: Data flows directly from sender to receiver via memory buffers
- **Automatic Cleanup**: Transfer data is automatically deleted after completion
- **Thread-Safe**: All operations use proper locking and condition variables

## Installation

1. Ensure Python 3.12+ is installed
2. Install dependencies:
```bash
pip install -r ../requirments.txt
```

## Running the Server

```bash
python server/app.py
```

Server will start on: `http://127.0.0.1:5000`

## Testing

Run the comprehensive test suite:

```bash
python server/test_server.py
```

This will test all endpoints and verify data integrity.

## API Endpoints

### Client Management

#### `POST /register`
Register a client with the server.

**Request:**
```json
{
  "client_id": "alice",
  "ip_address": "127.0.0.1"
}
```

**Response:** `201 Created`
```json
{
  "message": "Client registered successfully",
  "client_id": "alice"
}
```

#### `POST /heartbeat`
Update client's last-seen timestamp.

**Request:**
```json
{
  "client_id": "alice"
}
```

**Response:** `200 OK`

#### `GET /clients?client_id=alice`
Get list of active clients (excluding the requester).

**Response:** `200 OK`
```json
{
  "clients": [
    {
      "id": "bob",
      "ip": "127.0.0.1",
      "status": "Online"
    }
  ],
  "count": 1
}
```

### Transfer Signaling

#### `POST /request_transfer`
Sender initiates a file transfer.

**Request:**
```json
{
  "sender_id": "alice",
  "recipient_id": "bob",
  "metadata": {
    "filename": "document.pdf",
    "filesize": 1048576,
    "file_hash": "sha256hash...",
    "sk_bundle": "base64encryptedkey..."
  }
}
```

**Response:** `201 Created`
```json
{
  "token": "abc123xyz789",
  "message": "Transfer request created",
  "status": "PENDING"
}
```

#### `GET /check_requests/<client_id>`
Long-polling endpoint for receivers to wait for incoming transfers.

**Response (if request found):** `200 OK`
```json
{
  "has_request": true,
  "token": "abc123xyz789",
  "sender_id": "alice",
  "metadata": { ... }
}
```

**Response (timeout):** `204 No Content`

#### `POST /accept_transfer/<token>`
Receiver accepts the transfer.

**Response:** `200 OK`

#### `POST /reject_transfer/<token>`
Receiver rejects the transfer.

**Response:** `200 OK`

#### `GET /check_status/<token>`
Check the status of a transfer request.

**Response:** `200 OK`
```json
{
  "token": "abc123xyz789",
  "status": "ACCEPTED",
  "sender_id": "alice",
  "recipient_id": "bob"
}
```

### Data Streaming

#### `POST /stream_upload/<token>`
Sender uploads encrypted file data in chunks.

**Request:** Binary data stream (application/octet-stream)

**Response:** `200 OK`
```json
{
  "message": "Upload complete",
  "bytes_received": 1048576
}
```

#### `GET /stream_download/<token>`
Receiver downloads encrypted file data in chunks.

**Response:** Binary data stream (application/octet-stream)

#### `DELETE /delete/<token>`
Cleanup transfer data after completion.

**Response:** `200 OK`

### Utility

#### `GET /health`
Health check endpoint.

**Response:** `200 OK`
```json
{
  "status": "healthy"
}
```

#### `GET /status`
Server status and statistics.

**Response:** `200 OK`
```json
{
  "status": "online",
  "active_clients": 2,
  "active_transfers": 1,
  "max_transfers": 10,
  "pending_requests": 0
}
```

## Configuration

Edit these constants in the source files:

**`app.py`:**
- `SERVER_HOST` - Server bind address (default: 127.0.0.1)
- `SERVER_PORT` - Server port (default: 5000)
- `MAX_CONTENT_LENGTH` - Maximum upload size (default: 500 MB)

**`streaming.py`:**
- `CHUNK_SIZE` - Streaming chunk size (default: 64 KB)
- `MAX_CONCURRENT_TRANSFERS` - Maximum simultaneous transfers (default: 10)
- `BUFFER_MAX_SIZE` - Maximum chunks in memory per transfer (default: 100)

**`registry.py`:**
- `MAX_CLIENT_LIFETIME_SECONDS` - Client timeout (default: 300 seconds)

**`signaling.py`:**
- `REQUEST_TIMEOUT_SECONDS` - Transfer request timeout (default: 300 seconds)

## Security Considerations

1. **No Disk Storage**: Files never touch the server's disk
2. **Memory Only**: All data is kept in RAM and automatically cleaned up
3. **Opaque Metadata**: Server never sees encryption keys (passed as opaque data)
4. **Localhost Only**: Designed for single-machine testing (not exposed to network)
5. **No Authentication**: Suitable for localhost testing only

## Performance

- **Chunk Size**: 64 KB for optimal streaming performance
- **Concurrent Transfers**: Up to 10 simultaneous transfers
- **Buffer Management**: Producer-consumer pattern prevents memory overflow
- **Threading**: Full multi-threading support for handling concurrent clients

## Troubleshooting

### Server won't start
- Check if port 5000 is already in use
- Verify Python version is 3.12+
- Ensure Flask is installed: `pip install flask`

### Transfers timing out
- Check `REQUEST_TIMEOUT_SECONDS` and `MAX_CLIENT_LIFETIME_SECONDS`
- Verify both clients are sending heartbeats
- Ensure receiver accepts transfer quickly

### Memory usage high
- Reduce `BUFFER_MAX_SIZE` if handling large files
- Reduce `MAX_CONCURRENT_TRANSFERS` if memory constrained
- Check that transfers are completing and cleaning up properly

## Next Steps

The server is complete and fully tested. Next, implement the client application that will:

1. Connect to this server
2. Implement encryption/decryption (ML-KEM-768 + AES-256-GCM)
3. Provide CLI interface for users
4. Handle file chunking and streaming

See `../project_plan.md` for the complete implementation roadmap.

