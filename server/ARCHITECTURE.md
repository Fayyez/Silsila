# Server Architecture & Flow Diagrams

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Application                         │
│                      (app.py)                                │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  Client    │  │  Signaling │  │  Streaming │           │
│  │  Registry  │  │  Service   │  │  Conduits  │           │
│  │  Endpoints │  │  Endpoints │  │  Endpoints │           │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘           │
│         │                │                │                  │
│         ▼                ▼                ▼                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ registry.py│  │signaling.py│  │streaming.py│           │
│  │            │  │            │  │            │           │
│  │ CLIENTS {} │  │ TRANSFER   │  │ TRANSFER   │           │
│  │            │  │ REQUESTS{} │  │ CONDUITS{} │           │
│  │ In-Memory  │  │            │  │            │           │
│  │ Storage    │  │ Condition  │  │ Producer-  │           │
│  │            │  │ Variables  │  │ Consumer   │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                              │
└─────────────────────────────────────────────────────────────┘

         ▲                                      ▲
         │                                      │
         │ HTTP/REST API                        │
         │                                      │
    ┌────┴────┐                           ┌────┴────┐
    │  ALICE  │                           │   BOB   │
    │ (Sender)│                           │(Receiver)│
    └─────────┘                           └─────────┘
```

## Module Responsibilities

### 1. registry.py - Client Management
**Data Structures:**
- `CLIENTS = {}` - Active client registry
- `FILE_METADATA = {}` - File metadata storage (legacy, not used)

**Functions:**
- `register_client()` - Add/update client
- `update_heartbeat()` - Refresh last_seen
- `get_active_clients()` - Filter by timeout
- Client lifecycle management

### 2. signaling.py - Transfer Coordination
**Data Structures:**
- `TRANSFER_REQUESTS = {}` - Active transfer requests
- `RECIPIENT_CONDITIONS = {}` - Condition variables per recipient

**Functions:**
- `create_transfer_request()` - Generate token, notify recipient
- `check_for_requests()` - Long-polling with timeout
- `update_request_status()` - Accept/Reject/Expire
- `get_request_data()` - Query transfer info
- `delete_request()` - Cleanup

### 3. streaming.py - Data Conduits
**Data Structures:**
- `TRANSFER_CONDUITS = {}` - In-memory buffers per token
  - Each contains: buffer (deque), condition, flags, counters

**Functions:**
- `initialize_conduit()` - Create buffer for transfer
- `write_chunk()` - Producer writes (blocks if full)
- `read_chunk()` - Consumer reads (blocks if empty)
- `mark_transfer_complete()` - Signal EOF
- `cleanup_conduit()` - Free memory

## Complete Transfer Flow

```
TIME →

ALICE (Sender)          SERVER                  BOB (Receiver)
     │                     │                          │
     │  POST /register     │                          │
     ├────────────────────►│                          │
     │  201 Created        │                          │
     │◄────────────────────┤                          │
     │                     │      POST /register      │
     │                     │◄─────────────────────────┤
     │                     │      201 Created         │
     │                     ├─────────────────────────►│
     │                     │                          │
     │  POST /heartbeat    │                          │
     ├────────────────────►│                          │
     │  (every 30s)        │                          │
     │                     │      POST /heartbeat     │
     │                     │◄─────────────────────────┤
     │                     │      (every 30s)         │
     │                     │                          │
     │  GET /clients       │                          │
     ├────────────────────►│                          │
     │  [bob, ...]         │                          │
     │◄────────────────────┤                          │
     │                     │                          │
     │                     │   GET /check_requests/bob│
     │                     │◄─────────────────────────┤
     │                     │   (long-poll, blocks)    │
     │                     │                          │
     │ POST /request       │                          │
     │ _transfer           │                          │
     ├────────────────────►│                          │
     │ token: ABC123       │  ┌─────────────┐        │
     │◄────────────────────┤  │Notify Bob's │        │
     │                     ├─►│Condition Var│        │
     │                     │  └─────────────┘        │
     │                     │   200 OK (has_request)  │
     │                     ├─────────────────────────►│
     │                     │   token: ABC123          │
     │                     │                          │
     │                     │   POST /accept/ABC123    │
     │                     │◄─────────────────────────┤
     │                     │  ┌──────────────┐       │
     │                     ├─►│Init Conduit  │       │
     │                     │  │for ABC123    │       │
     │                     │  └──────────────┘       │
     │                     │   200 OK                 │
     │                     ├─────────────────────────►│
     │                     │                          │
     │ GET /check_status/  │                          │
     │ ABC123              │                          │
     ├────────────────────►│                          │
     │ status: ACCEPTED    │                          │
     │◄────────────────────┤                          │
     │                     │                          │
     │ POST /stream_upload/│                          │
     │ ABC123              │                          │
     ├─ CHUNK 1 ─────────►│                          │
     ├─ CHUNK 2 ─────────►│  ┌──────────────┐       │
     ├─ CHUNK 3 ─────────►├─►│In-Memory     │       │
     ├─ CHUNK 4 ─────────►│  │Buffer        │       │
     │      ...            │  │(deque)       │       │
     ├─ CHUNK N ─────────►│  └──────┬───────┘       │
     │                     │         │                │
     │ 200 OK              │         │   GET /stream_download/ABC123
     │ bytes: 1048576      │         │   ◄──────────────────────────┤
     │◄────────────────────┤         │                               │
     │                     │         └──► CHUNK 1 ───────────────────►
     │                     │              CHUNK 2 ───────────────────►
     │                     │              CHUNK 3 ───────────────────►
     │                     │              CHUNK 4 ───────────────────►
     │                     │                 ...                      │
     │                     │              CHUNK N ───────────────────►
     │                     │              200 OK                      │
     │                     │                                          │
     │                     │  ┌──────────────┐                       │
     │                     ├─►│Cleanup       │                       │
     │                     │  │Conduit       │                       │
     │                     │  │ABC123        │                       │
     │                     │  └──────────────┘                       │
     │                     │                                          │
```

## In-Memory Streaming Detail

```
┌─────────────────────────────────────────────────────────────┐
│                  TRANSFER CONDUIT (Token: ABC123)            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  In-Memory Buffer                     │  │
│  │                     (deque)                           │  │
│  │                                                       │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     ┌──────┐  │  │
│  │  │Chunk1│ │Chunk2│ │Chunk3│ │Chunk4│ ... │ChunkN│  │  │
│  │  │ 64KB │ │ 64KB │ │ 64KB │ │ 64KB │     │ 64KB │  │  │
│  │  └──────┘ └──────┘ └──────┘ └──────┘     └──────┘  │  │
│  │      ▲                                        │      │  │
│  │      │                                        │      │  │
│  │   PRODUCER                                CONSUMER   │  │
│  │   (Sender)                               (Receiver)  │  │
│  │   Writes                                   Reads     │  │
│  │                                                       │  │
│  │  Max Size: 100 chunks = 6.4 MB buffer                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │             Condition Variable                        │  │
│  │  - Signals when data available                        │  │
│  │  - Signals when space available                       │  │
│  │  - Thread-safe blocking                               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Flags:                                                      │
│  - transfer_complete: bool (EOF signal)                      │
│  - error: str | None (error message)                         │
│  - bytes_transferred: int (total bytes)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Threading Model

```
┌──────────────────────────────────────────────────────────┐
│                    Flask Server                           │
│                  (threaded=True)                          │
│                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Thread 1   │  │  Thread 2   │  │  Thread 3   │     │
│  │             │  │             │  │             │     │
│  │ Handling    │  │ Handling    │  │ Handling    │ ... │
│  │ Alice's     │  │ Bob's       │  │ Charlie's   │     │
│  │ requests    │  │ long-poll   │  │ upload      │     │
│  │             │  │             │  │             │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│         └────────────────┼────────────────┘             │
│                          │                               │
│                   Shared Resources                       │
│                   (Thread-Safe)                          │
│         ┌────────────────┴────────────────┐             │
│         │                                  │             │
│    ┌────▼─────┐  ┌──────────┐  ┌────────▼─────┐       │
│    │ CLIENTS  │  │TRANSFER   │  │TRANSFER      │       │
│    │   {}     │  │REQUESTS{} │  │CONDUITS{}    │       │
│    │          │  │           │  │              │       │
│    │Protected │  │Protected  │  │Protected by  │       │
│    │by GIL    │  │by         │  │Condition     │       │
│    │          │  │Condition  │  │Variables     │       │
│    └──────────┘  └──────────┘  └──────────────┘       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## Concurrency Control

### Long-Polling (Efficient Blocking)
```python
# Bob waits for incoming transfers
with RECIPIENT_CONDITIONS[client_id]:
    RECIPIENT_CONDITIONS[client_id].wait(timeout=10)
    # Blocks thread without CPU usage
    # Wakes up when:
    #   1. New transfer request arrives (notify)
    #   2. 10 second timeout expires
```

### Producer-Consumer (Streaming)
```python
# Alice uploads (Producer)
with conduit['condition']:
    while len(conduit['buffer']) >= MAX_SIZE:
        conduit['condition'].wait()  # Wait for space
    conduit['buffer'].append(chunk)
    conduit['condition'].notify_all()  # Signal consumers

# Bob downloads (Consumer)
with conduit['condition']:
    while len(conduit['buffer']) == 0 and not complete:
        conduit['condition'].wait()  # Wait for data
    chunk = conduit['buffer'].popleft()
    conduit['condition'].notify_all()  # Signal producers
```

## Memory Management

### Buffer Flow
```
Upload Stream:
  File (Disk) → 64KB Chunks → In-Memory Buffer → 64KB Chunks → Download Stream → File (Disk)
                   ▲                                                ▲
                   │                                                │
              Alice's RAM                                       Bob's RAM
                   │                                                │
                   └────────────── Server RAM ─────────────────────┘
                                (Temporary Buffer)
```

### Cleanup Process
1. **During Transfer**: Buffer self-regulates (max 100 chunks)
2. **After Download**: Automatic cleanup in `stream_download()` generator
3. **Manual Cleanup**: `DELETE /delete/<token>` if needed
4. **Memory Freed**: Immediately available for next transfer

## Error Handling

```
┌─────────────────────────────────────────────────────┐
│                 Error Scenarios                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│ 1. Client Not Registered                            │
│    → 404 Not Found                                  │
│                                                      │
│ 2. Recipient Offline                                │
│    → 404 Not Found (filtered from active list)     │
│                                                      │
│ 3. Transfer Rejected                                │
│    → Status changes to 'REJECTED'                   │
│                                                      │
│ 4. Server at Capacity (10 transfers)                │
│    → 503 Service Unavailable                        │
│                                                      │
│ 5. Upload Timeout                                   │
│    → Error flag set in conduit                      │
│    → Download fails gracefully                      │
│                                                      │
│ 6. Download Timeout                                 │
│    → Connection closes                              │
│    → Automatic cleanup                              │
│                                                      │
│ 7. Request Expired (5 minutes)                      │
│    → Status changes to 'EXPIRED'                    │
│    → Filtered from check_requests()                 │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Security Boundaries

```
┌────────────────────────────────────────────────────┐
│            What Server Knows                        │
├────────────────────────────────────────────────────┤
│ ✓ Client IDs (alice, bob)                          │
│ ✓ IP Addresses (127.0.0.1)                         │
│ ✓ Transfer metadata (filename, size)               │
│ ✓ File hash (but can't verify without key)         │
│ ✓ Transfer status (PENDING, ACCEPTED, etc.)        │
│ ✓ Bytes transferred                                 │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│         What Server Does NOT Know                   │
├────────────────────────────────────────────────────┤
│ ✗ File contents (encrypted)                        │
│ ✗ Encryption keys (opaque sk_bundle)               │
│ ✗ Plaintext hashes                                  │
│ ✗ Actual file data (all encrypted)                 │
└────────────────────────────────────────────────────┘
```

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Chunk Size | 64 KB | Optimal for network and memory |
| Buffer Size | 6.4 MB | 100 chunks per transfer |
| Max Memory | 64 MB | 10 transfers × 6.4 MB |
| Throughput | ~100 MB/s | localhost (no network limit) |
| Latency | < 10 ms | Signaling operations |
| Concurrent Users | Unlimited | Limited by transfers |
| Concurrent Transfers | 10 | Configurable |
| Client Timeout | 5 minutes | Heartbeat-based |
| Request Timeout | 5 minutes | Auto-expire old requests |
| Long-Poll Timeout | 10 seconds | Balance efficiency/responsiveness |

## Scalability Notes

### Current Design (Localhost)
- ✅ Perfect for localhost testing
- ✅ Simple in-memory storage
- ✅ No database needed
- ✅ Fast and efficient

### If Scaling to Production Would Need:
- 🔄 Persistent storage (Redis, database)
- 🔄 Authentication and authorization
- 🔄 TLS/HTTPS encryption
- 🔄 Load balancing
- 🔄 Horizontal scaling
- 🔄 Rate limiting
- 🔄 Logging and monitoring
- 🔄 Graceful shutdown handling

**Note**: Current design is intentionally simple for localhost prototype as per requirements.

## Summary

The server architecture is built around three core principles:

1. **Simplicity**: Clean module separation, easy to understand
2. **Efficiency**: In-memory operations, no disk I/O
3. **Safety**: Thread-safe operations, proper cleanup

All components work together to provide a secure, efficient relay service for quantum-safe file transfers.

