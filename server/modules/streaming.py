import threading
import time
from collections import deque

# Configuration
CHUNK_SIZE = 64 * 1024  # 64 KB chunks
MAX_CONCURRENT_TRANSFERS = 10
BUFFER_MAX_SIZE = 100  # Maximum number of chunks to hold in memory per transfer

# Dictionary to hold active streaming conduits
# Key: Transfer Token (str)
# Value: {
#     'buffer': deque,
#     'condition': threading.Condition,
#     'transfer_complete': bool,
#     'error': str | None,
#     'bytes_transferred': int
# }
TRANSFER_CONDUITS = {}
CONDUIT_LOCK = threading.Lock()


def initialize_conduit(token: str) -> bool:
    """
    Initializes an in-memory streaming conduit for a transfer token.
    Returns False if max concurrent transfers reached.
    """
    with CONDUIT_LOCK:
        if len(TRANSFER_CONDUITS) >= MAX_CONCURRENT_TRANSFERS:
            print(f"[STREAMING ERROR] Max concurrent transfers ({MAX_CONCURRENT_TRANSFERS}) reached.")
            return False
        
        if token not in TRANSFER_CONDUITS:
            TRANSFER_CONDUITS[token] = {
                'buffer': deque(),
                'condition': threading.Condition(),
                'transfer_complete': False,
                'error': None,
                'bytes_transferred': 0
            }
            print(f"[STREAMING] Conduit initialized for token: {token}")
            return True
        return True


def write_chunk(token: str, chunk_data: bytes) -> bool:
    """
    Writes a chunk of data to the conduit buffer (Producer).
    Blocks if buffer is full.
    """
    if token not in TRANSFER_CONDUITS:
        print(f"[STREAMING ERROR] Token {token} not found in conduits.")
        return False
    
    conduit = TRANSFER_CONDUITS[token]
    
    with conduit['condition']:
        # Wait if buffer is full
        while len(conduit['buffer']) >= BUFFER_MAX_SIZE:
            conduit['condition'].wait(timeout=1.0)
            
            # Check if transfer was cancelled
            if conduit.get('error'):
                return False
        
        # Add chunk to buffer
        conduit['buffer'].append(chunk_data)
        conduit['bytes_transferred'] += len(chunk_data)
        
        # Notify waiting consumers
        conduit['condition'].notify_all()
    
    return True


def read_chunk(token: str, timeout: float = 30.0) -> bytes | None:
    """
    Reads a chunk from the conduit buffer (Consumer).
    Returns None if transfer is complete and buffer is empty.
    Blocks if buffer is empty and transfer is not complete.
    """
    if token not in TRANSFER_CONDUITS:
        print(f"[STREAMING ERROR] Token {token} not found in conduits.")
        return None
    
    conduit = TRANSFER_CONDUITS[token]
    start_time = time.time()
    
    with conduit['condition']:
        # Wait while buffer is empty and transfer is not complete
        while len(conduit['buffer']) == 0 and not conduit['transfer_complete']:
            remaining_timeout = timeout - (time.time() - start_time)
            
            if remaining_timeout <= 0:
                print(f"[STREAMING WARNING] Read timeout for token {token}")
                return None
            
            conduit['condition'].wait(timeout=min(remaining_timeout, 1.0))
            
            # Check for errors
            if conduit.get('error'):
                print(f"[STREAMING ERROR] Transfer error: {conduit['error']}")
                return None
        
        # If buffer is empty and transfer is complete, we're done
        if len(conduit['buffer']) == 0 and conduit['transfer_complete']:
            return None
        
        # Get chunk from buffer
        if len(conduit['buffer']) > 0:
            chunk = conduit['buffer'].popleft()
            
            # Notify producer that space is available
            conduit['condition'].notify_all()
            return chunk
    
    return None


def mark_transfer_complete(token: str):
    """
    Marks the transfer as complete (called by producer when done uploading).
    """
    if token in TRANSFER_CONDUITS:
        conduit = TRANSFER_CONDUITS[token]
        with conduit['condition']:
            conduit['transfer_complete'] = True
            conduit['condition'].notify_all()
            print(f"[STREAMING] Transfer marked complete for token: {token}")


def mark_transfer_error(token: str, error_message: str):
    """
    Marks the transfer as failed with an error message.
    """
    if token in TRANSFER_CONDUITS:
        conduit = TRANSFER_CONDUITS[token]
        with conduit['condition']:
            conduit['error'] = error_message
            conduit['condition'].notify_all()
            print(f"[STREAMING ERROR] Transfer failed for token {token}: {error_message}")


def cleanup_conduit(token: str):
    """
    Removes the conduit from memory after transfer is complete.
    """
    with CONDUIT_LOCK:
        if token in TRANSFER_CONDUITS:
            bytes_transferred = TRANSFER_CONDUITS[token]['bytes_transferred']
            del TRANSFER_CONDUITS[token]
            print(f"[STREAMING] Conduit cleaned up for token {token}. Total bytes: {bytes_transferred}")
            return True
    return False


def get_conduit_status(token: str) -> dict | None:
    """
    Returns status information about a conduit.
    """
    if token in TRANSFER_CONDUITS:
        conduit = TRANSFER_CONDUITS[token]
        with conduit['condition']:
            return {
                'buffer_size': len(conduit['buffer']),
                'transfer_complete': conduit['transfer_complete'],
                'bytes_transferred': conduit['bytes_transferred'],
                'error': conduit.get('error')
            }
    return None


def get_active_transfer_count() -> int:
    """
    Returns the number of currently active transfers.
    """
    with CONDUIT_LOCK:
        return len(TRANSFER_CONDUITS)

