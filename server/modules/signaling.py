import time
import base64
import os
import threading

# Dictionary to hold active transfer requests
# Key: Transfer Token (str)
# Value: { recipient_id: str, sender_id: str, status: str, metadata: dict, timestamp: float, condition: threading.Condition }
TRANSFER_REQUESTS = {}
REQUEST_TIMEOUT_SECONDS = 300 # Request expires after 5 minutes

# Dictionary to map recipient ID to their Condition object for fast signaling
# Key: client_id (str)
# Value: threading.Condition object
RECIPIENT_CONDITIONS = {} 


def create_transfer_request(sender_id: str, recipient_id: str, metadata: dict) -> str:
    """Creates a new transfer request and notifies the recipient."""
    
    # 1. Generate unique transfer token
    transfer_token = base64.urlsafe_b64encode(os.urandom(8)).decode('utf-8')
    
    # 2. Get or create the recipient's condition variable
    if recipient_id not in RECIPIENT_CONDITIONS:
        RECIPIENT_CONDITIONS[recipient_id] = threading.Condition()

    # 3. Store the request
    TRANSFER_REQUESTS[transfer_token] = {
        'recipient_id': recipient_id,
        'sender_id': sender_id,
        'status': 'PENDING',
        'metadata': metadata, # Includes SK Bundle, filename, size, hash
        'timestamp': time.time(),
        'condition': threading.Condition(), # Condition specific to the transfer stream itself
    }
    
    print(f"[SIGNAL] Request created (Token: {transfer_token}) from {sender_id} to {recipient_id}")

    # 4. Signal the waiting recipient
    with RECIPIENT_CONDITIONS[recipient_id]:
        RECIPIENT_CONDITIONS[recipient_id].notify_all()
        
    return transfer_token

def check_for_requests(client_id: str, timeout: int = 10) -> dict | None:
    """
    Blocks until a new request is available for the client_id or timeout occurs.
    Implements the Long-Polling mechanism.
    """
    if client_id not in RECIPIENT_CONDITIONS:
        RECIPIENT_CONDITIONS[client_id] = threading.Condition()
    
    with RECIPIENT_CONDITIONS[client_id]:
        # Wait for notification or timeout
        RECIPIENT_CONDITIONS[client_id].wait(timeout=timeout)
    
    # After waking up, check the requests
    for token, request_data in TRANSFER_REQUESTS.items():
        if request_data['recipient_id'] == client_id and request_data['status'] == 'PENDING':
            # Check if the request is too old
            if time.time() - request_data['timestamp'] > REQUEST_TIMEOUT_SECONDS:
                request_data['status'] = 'EXPIRED'
                continue

            return {
                'token': token,
                'sender_id': request_data['sender_id'],
                'metadata': request_data['metadata']
            }
            
    return None

def update_request_status(token: str, status: str) -> bool:
    """Updates the status of a specific transfer request (e.g., ACCEPTED, REJECTED)."""
    if token in TRANSFER_REQUESTS:
        TRANSFER_REQUESTS[token]['status'] = status
        print(f"[SIGNAL] Transfer Token {token} status updated to: {status}")
        return True
    return False

def get_request_data(token: str) -> dict | None:
    """Retrieves data for a specific token."""
    return TRANSFER_REQUESTS.get(token)

def delete_request(token: str):
    """Cleans up the transfer request."""
    if token in TRANSFER_REQUESTS:
        del TRANSFER_REQUESTS[token]
        print(f"[SIGNAL] Transfer request deleted: {token}")
