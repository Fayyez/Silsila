import time
import base64
import os

# In-memory dictionary to store client status and metadata
# Structure: { client_id: { 'ip_address': str, 'last_seen': float, 'status': str } }
CLIENTS = {}
FILE_METADATA = {} 
MAX_CLIENT_LIFETIME_SECONDS = 300 # 5 minutes

def register_client(client_id: str, ip_address: str):
    """Adds or updates a client's presence."""
    
    CLIENTS[client_id] = {
        'ip_address': ip_address,
        'last_seen': time.time(),
        'status': 'Online'
    }
    print(f"[REGISTRY] Client registered: {client_id} at {ip_address}")

def update_heartbeat(client_id: str) -> bool:
    """Updates the last_seen timestamp for a client."""
    if client_id in CLIENTS:
        CLIENTS[client_id]['last_seen'] = time.time()
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
