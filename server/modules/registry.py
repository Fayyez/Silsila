import time
import base64
import os
import json
import queue
import threading

# In-memory dictionary to store client status and metadata
# Structure: { client_id: { 'ip_address': str, 'socket_number': str, 'last_seen': float, 'status': str } }
CLIENTS = {}
FILE_METADATA = {} 
MAX_CLIENT_LIFETIME_SECONDS = 300 # 5 minutes

# Subscription queues for real-time updates
# Each client connecting to SSE gets a queue
SUBSCRIBERS = []
SUBSCRIBERS_LOCK = threading.Lock()

def subscribe() -> queue.Queue:
    """Subscribe to registry change notifications."""
    q = queue.Queue()
    with SUBSCRIBERS_LOCK:
        SUBSCRIBERS.append(q)
    return q

def unsubscribe(q: queue.Queue):
    """Unsubscribe from registry change notifications."""
    with SUBSCRIBERS_LOCK:
        if q in SUBSCRIBERS:
            SUBSCRIBERS.remove(q)

def _notify_subscribers():
    """Notify all subscribers of a registry change."""
    # Just put a simple notification - let each SSE connection compute its own client list
    update = {
        'type': 'registry_update',
        'timestamp': time.time()
    }
    
    with SUBSCRIBERS_LOCK:
        for q in SUBSCRIBERS:
            try:
                q.put_nowait(update)
            except queue.Full:
                pass  # Skip if queue is full

def _print_registry():
    """Helper function to print the current registry state."""
    print("\n" + "="*70)
    print("[REGISTRY STATE]")
    if not CLIENTS:
        print("  No clients connected")
    else:
        print(f"  Total clients: {len(CLIENTS)}")
        for client_id, data in CLIENTS.items():
            elapsed = time.time() - data.get('last_seen', 0)
            print(f"    - {client_id}")
            print(f"      IP: {data.get('ip_address')}")
            print(f"      Socket: {data.get('socket_number')}")
            print(f"      Status: {data.get('status')}")
            print(f"      Last seen: {elapsed:.1f}s ago")
    print("="*70 + "\n")

def register_client(client_id: str, ip_address: str, socket_number: str = None):
    """
    Adds or updates a client's presence.
    If a client with the same IP and socket exists, replace the old one.
    """
    
    # Check if there's an existing client with the same IP and socket
    if socket_number:
        old_client_id = find_client_by_ip_and_socket(ip_address, socket_number)
        if old_client_id and old_client_id != client_id:
            print(f"[REGISTRY] Replacing old connection: {old_client_id} from {ip_address}:{socket_number}")
            del CLIENTS[old_client_id]
    
    CLIENTS[client_id] = {
        'ip_address': ip_address,
        'socket_number': socket_number,
        'last_seen': time.time(),
        'status': 'Online'
    }
    print(f"[REGISTRY] Client registered: {client_id} at {ip_address}:{socket_number}")
    _print_registry()
    _notify_subscribers()

def find_client_by_ip_and_socket(ip_address: str, socket_number: str) -> str | None:
    """Finds a client by IP address and socket number."""
    for client_id, client_data in CLIENTS.items():
        if (client_data.get('ip_address') == ip_address and 
            client_data.get('socket_number') == socket_number):
            return client_id
    return None

def update_heartbeat(client_id: str) -> bool:
    """Updates the last_seen timestamp for a client."""
    if client_id in CLIENTS:
        CLIENTS[client_id]['last_seen'] = time.time()
        _print_registry()
        # _notify_subscribers()
        return True
    return False

def get_active_clients(current_client_id: str = None) -> list:
    """Returns a list of clients considered 'Online' (recent heartbeat)."""
    active_list = []
    now = time.time()
    
    for client_id, client_data in CLIENTS.items():
        if client_id == current_client_id:
            continue
            
        last_seen = client_data.get('last_seen', 0)
        
        if (now - last_seen) < MAX_CLIENT_LIFETIME_SECONDS:
            active_list.append({
                'id': client_id,
                'ip': client_data['ip_address'],
                'status': 'Online'
            })
    return active_list

def add_file_metadata(file_data: dict) -> str:
    """Generates a unique ID and stores file transfer metadata."""
    file_id = base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')
    FILE_METADATA[file_id] = file_data
    return file_id

def get_file_metadata(file_id: str) -> dict | None:
    """Retrieves metadata for a specific file ID."""
    return FILE_METADATA.get(file_id)

def list_pending_files(recipient_id: str) -> list:
    """Lists files uploaded for the given recipient ID."""
    pending = []
    for file_id, data in FILE_METADATA.items():
        if data['recipient_id'] == recipient_id:
            pending.append({
                'file_id': file_id,
                'sender_id': data['sender_id'],
                'original_filename': data['original_filename'],
                'uploaded_at': data['uploaded_at']
            })
    return pending

def delete_file_metadata(file_id: str) -> bool:
    """Deletes file metadata after successful download."""
    if file_id in FILE_METADATA:
        del FILE_METADATA[file_id]
        return True
    return False
