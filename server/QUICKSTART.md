# Server Quick Start Guide

## Start the Server

```bash
# From project root
python server/app.py
```

You should see:
```
============================================================
Quantum-Safe File Sharing Server
============================================================
Starting server on 127.0.0.1:5000
Max concurrent transfers: 10
Chunk size: 65536 bytes
============================================================
```

## Test the Server

Run the test suite:
```bash
python server/test_server.py
```

Expected output:
```
ALL TESTS PASSED! ✓
Server is working correctly and ready for client implementation.
```

## Protocol Flow Example

Here's how a complete file transfer works:

### 1. Both Clients Register

**Alice (Sender):**
```python
import requests

requests.post('http://127.0.0.1:5000/register', json={
    'client_id': 'alice',
    'ip_address': '127.0.0.1'
})
```

**Bob (Receiver):**
```python
requests.post('http://127.0.0.1:5000/register', json={
    'client_id': 'bob',
    'ip_address': '127.0.0.1'
})
```

### 2. Both Send Heartbeats (Periodically)

```python
# Every 30 seconds
requests.post('http://127.0.0.1:5000/heartbeat', json={
    'client_id': 'alice'
})
```

### 3. Alice Lists Online Clients

```python
response = requests.get('http://127.0.0.1:5000/clients?client_id=alice')
print(response.json())
# Output: {"clients": [{"id": "bob", "ip": "127.0.0.1", "status": "Online"}]}
```

### 4. Alice Initiates Transfer

```python
response = requests.post('http://127.0.0.1:5000/request_transfer', json={
    'sender_id': 'alice',
    'recipient_id': 'bob',
    'metadata': {
        'filename': 'document.pdf',
        'filesize': 1048576,
        'file_hash': 'sha256...',
        'sk_bundle': 'encrypted_key_data...'
    }
})

token = response.json()['token']
print(f"Transfer token: {token}")
```

### 5. Bob Checks for Requests (Long-Polling)

```python
# This blocks for up to 10 seconds
response = requests.get('http://127.0.0.1:5000/check_requests/bob')

if response.status_code == 200:
    data = response.json()
    token = data['token']
    sender = data['sender_id']
    metadata = data['metadata']
    print(f"Incoming file from {sender}: {metadata['filename']}")
```

### 6. Bob Accepts the Transfer

```python
response = requests.post(f'http://127.0.0.1:5000/accept_transfer/{token}')
# Server initializes streaming conduit
```

### 7. Alice Checks Status (Optional)

```python
response = requests.get(f'http://127.0.0.1:5000/check_status/{token}')
status = response.json()['status']  # Should be 'ACCEPTED'
```

### 8. Alice Uploads the File

```python
# Read file in chunks
with open('document.pdf', 'rb') as f:
    file_data = f.read()

response = requests.post(
    f'http://127.0.0.1:5000/stream_upload/{token}',
    data=file_data,
    headers={'Content-Type': 'application/octet-stream'}
)

print(f"Uploaded {response.json()['bytes_received']} bytes")
```

### 9. Bob Downloads the File

```python
response = requests.get(
    f'http://127.0.0.1:5000/stream_download/{token}',
    stream=True
)

with open('received_document.pdf', 'wb') as f:
    for chunk in response.iter_content(chunk_size=65536):
        f.write(chunk)

print("Download complete!")
```

### 10. Cleanup (Automatic)

The server automatically cleans up the streaming conduit and transfer data when the download completes.

## Common Patterns

### Heartbeat Loop (Run in Background Thread)

```python
import time
import threading

def heartbeat_loop(client_id):
    while True:
        try:
            requests.post('http://127.0.0.1:5000/heartbeat', json={
                'client_id': client_id
            }, timeout=5)
        except:
            pass
        time.sleep(30)  # Every 30 seconds

# Start in background
threading.Thread(target=heartbeat_loop, args=('alice',), daemon=True).start()
```

### Long-Polling Loop (Receiver)

```python
def wait_for_transfers(client_id):
    while True:
        try:
            response = requests.get(
                f'http://127.0.0.1:5000/check_requests/{client_id}',
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['has_request']:
                    handle_incoming_transfer(data)
                    
        except:
            time.sleep(1)  # Brief pause on error
```

### Chunked Upload (Memory Efficient)

```python
def upload_file(token, file_path, chunk_size=65536):
    with open(file_path, 'rb') as f:
        def generate_chunks():
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        
        response = requests.post(
            f'http://127.0.0.1:5000/stream_upload/{token}',
            data=generate_chunks(),
            headers={'Content-Type': 'application/octet-stream'}
        )
    return response.json()
```

### Chunked Download (Memory Efficient)

```python
def download_file(token, save_path, chunk_size=65536):
    response = requests.get(
        f'http://127.0.0.1:5000/stream_download/{token}',
        stream=True
    )
    
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
```

## Error Handling

### Check if Recipient is Online

```python
response = requests.get('http://127.0.0.1:5000/clients?client_id=alice')
clients = response.json()['clients']
recipient_ids = [c['id'] for c in clients]

if 'bob' not in recipient_ids:
    print("Error: Recipient is offline")
```

### Handle Transfer Rejection

```python
# After requesting transfer, poll for status
for _ in range(30):  # Check for 30 seconds
    response = requests.get(f'http://127.0.0.1:5000/check_status/{token}')
    status = response.json()['status']
    
    if status == 'ACCEPTED':
        # Proceed with upload
        break
    elif status == 'REJECTED':
        print("Transfer was rejected")
        break
    
    time.sleep(1)
```

### Handle Server Capacity Limit

```python
response = requests.post(f'http://127.0.0.1:5000/accept_transfer/{token}')

if response.status_code == 503:
    print("Server at maximum capacity. Try again later.")
```

## Next Steps

1. ✅ Server is complete and tested
2. ⏭️ Implement client-side encryption (Phase 1 of project_plan.md)
3. ⏭️ Build CLI interface (Phase 4 of project_plan.md)
4. ⏭️ Integrate everything into a working application

See the main project plan for detailed implementation steps.

