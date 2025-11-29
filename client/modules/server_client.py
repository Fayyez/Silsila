"""
Server communication module for Quantum-Safe File Sharing client.
Handles all interactions with the central server.
"""

import requests
import threading
import time
from typing import Callable, Optional

SERVER_URL = "http://127.0.0.1:5000"
HEARTBEAT_INTERVAL = 30  # seconds
CHUNK_SIZE = 64 * 1024  # 64 KB


class ServerClient:
    """Handles communication with the central server."""
    
    def __init__(self, client_id: str, ip_address: str = "127.0.0.1", socket_number: str = None):
        """
        Initialize the server client.
        
        Args:
            client_id: Unique identifier for this client
            ip_address: IP address of this client
            socket_number: Optional socket number (host:port) that this client is listening on
        """
        self.client_id = client_id
        self.ip_address = ip_address
        self.socket_number = socket_number
        self.heartbeat_thread = None
        self.heartbeat_active = False
        self.poll_thread = None
        self.poll_active = False
        self.transfer_callback = None
    
    def register(self) -> bool:
        """
        Register this client with the server.
        
        Returns:
            bool: True if registration successful
        """
        try:
            # Use the socket_number provided during initialization, or try to get it
            socket_number = self.socket_number or self._get_socket_number()
            
            response = requests.post(
                f"{SERVER_URL}/register",
                json={
                    "client_id": self.client_id,
                    "ip_address": self.ip_address,
                    "socket_number": socket_number
                },
                timeout=10
            )
            
            if response.status_code == 201:
                print(f"✓ Registered as '{self.client_id}'")
                return True
            else:
                print(f"✗ Registration failed: {response.json().get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"✗ Registration error: {e}")
            return False
    
    def _get_socket_number(self) -> str:
        """
        Get the socket number from the client's listening socket.
        This is used as fallback if socket_number wasn't provided.
        
        Returns:
            str: Socket number in format 'host:port'
        """
        try:
            import socket as sock
            # Get a socket to extract local port information
            s = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
            s.bind((self.ip_address, 0))
            local_port = s.getsockname()[1]
            s.close()
            return f"{self.ip_address}:{local_port}"
        except Exception as e:
            # Fallback: return just IP if socket extraction fails
            print(f"⚠ Could not get socket number: {e}")
            return self.ip_address
    
    def start_heartbeat(self):
        """Start sending heartbeat signals to the server."""
        if self.heartbeat_active:
            return
        
        self.heartbeat_active = True
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self.heartbeat_thread.start()
        print("✓ Heartbeat started")
    
    def stop_heartbeat(self):
        """Stop sending heartbeat signals."""
        self.heartbeat_active = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
    
    def _heartbeat_loop(self):
        """Background loop for sending heartbeats."""
        while self.heartbeat_active:
            try:
                response = requests.post(
                    f"{SERVER_URL}/heartbeat",
                    json={"client_id": self.client_id},
                    timeout=5
                )
                
                if response.status_code != 200:
                    print(f"⚠ Heartbeat failed: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠ Heartbeat error: {e}")
            
            time.sleep(HEARTBEAT_INTERVAL)
    
    def get_online_clients(self) -> list:
        """
        Get list of online clients (excluding self).
        
        Returns:
            list: List of online client dictionaries
        """
        try:
            response = requests.get(
                f"{SERVER_URL}/clients",
                params={"client_id": self.client_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('clients', [])
            else:
                return []
                
        except Exception as e:
            print(f"✗ Error fetching clients: {e}")
            return []
    
    def request_transfer(self, recipient_id: str, metadata: dict) -> Optional[str]:
        """
        Initiate a file transfer request.
        
        Args:
            recipient_id: ID of the recipient client
            metadata: File metadata including filename, size, hash, sk_bundle
            
        Returns:
            str: Transfer token if successful, None otherwise
        """
        try:
            response = requests.post(
                f"{SERVER_URL}/request_transfer",
                json={
                    "sender_id": self.client_id,
                    "recipient_id": recipient_id,
                    "metadata": metadata
                },
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                return data['token']
            else:
                error = response.json().get('error', 'Unknown error')
                print(f"✗ Transfer request failed: {error}")
                return None
                
        except Exception as e:
            print(f"✗ Transfer request error: {e}")
            return None
    
    def check_transfer_status(self, token: str) -> Optional[str]:
        """
        Check the status of a transfer request.
        
        Args:
            token: Transfer token
            
        Returns:
            str: Status (PENDING, ACCEPTED, REJECTED, etc.) or None
        """
        try:
            response = requests.get(
                f"{SERVER_URL}/check_status/{token}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['status']
            else:
                return None
                
        except Exception as e:
            print(f"✗ Status check error: {e}")
            return None
    
    def wait_for_acceptance(self, token: str, timeout: int = 60) -> bool:
        """
        Wait for recipient to accept the transfer.
        
        Args:
            token: Transfer token
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if accepted, False if rejected or timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.check_transfer_status(token)
            
            if status == 'ACCEPTED':
                return True
            elif status == 'REJECTED':
                print("✗ Transfer was rejected by recipient")
                return False
            
            time.sleep(1)
        
        print("✗ Transfer acceptance timeout")
        return False
    
    def upload_file(self, token: str, file_path: str, progress_callback: Callable = None) -> bool:
        """
        Upload an encrypted file to the server.
        
        Args:
            token: Transfer token
            file_path: Path to the encrypted file
            progress_callback: Optional callback(bytes_sent, total_bytes)
            
        Returns:
            bool: True if upload successful
        """
        try:
            file_size = os.path.getsize(file_path)
            bytes_sent = 0
            
            def generate_chunks():
                nonlocal bytes_sent
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        bytes_sent += len(chunk)
                        
                        if progress_callback:
                            progress_callback(bytes_sent, file_size)
                        
                        yield chunk
            
            response = requests.post(
                f"{SERVER_URL}/stream_upload/{token}",
                data=generate_chunks(),
                headers={'Content-Type': 'application/octet-stream'},
                timeout=300
            )
            
            if response.status_code == 200:
                print(f"✓ Upload complete: {bytes_sent} bytes")
                return True
            else:
                error = response.json().get('error', 'Unknown error')
                print(f"✗ Upload failed: {error}")
                return False
                
        except Exception as e:
            print(f"✗ Upload error: {e}")
            return False
    
    def download_file(self, token: str, output_path: str, progress_callback: Callable = None) -> bool:
        """
        Download an encrypted file from the server.
        
        Args:
            token: Transfer token
            output_path: Path to save the encrypted file
            progress_callback: Optional callback(bytes_received, total_bytes)
            
        Returns:
            bool: True if download successful
        """
        try:
            response = requests.get(
                f"{SERVER_URL}/stream_download/{token}",
                stream=True,
                timeout=300
            )
            
            if response.status_code != 200:
                print(f"✗ Download failed: {response.status_code}")
                return False
            
            bytes_received = 0
            # Try to get total size from headers (may not be available)
            total_size = int(response.headers.get('Content-Length', 0))
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        bytes_received += len(chunk)
                        
                        if progress_callback:
                            progress_callback(bytes_received, total_size or bytes_received)
            
            print(f"✓ Download complete: {bytes_received} bytes")
            return True
            
        except Exception as e:
            print(f"✗ Download error: {e}")
            return False
    
    def start_listening(self, callback: Callable):
        """
        Start listening for incoming transfer requests.
        
        Args:
            callback: Function to call when request received
                     callback(token, sender_id, metadata)
        """
        if self.poll_active:
            return
        
        self.transfer_callback = callback
        self.poll_active = True
        self.poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True
        )
        self.poll_thread.start()
        print("✓ Listening for incoming transfers")
    
    def stop_listening(self):
        """Stop listening for incoming transfers."""
        self.poll_active = False
        if self.poll_thread:
            self.poll_thread.join(timeout=5)
    
    def _poll_loop(self):
        """Background loop for checking incoming requests."""
        while self.poll_active:
            try:
                response = requests.get(
                    f"{SERVER_URL}/check_requests/{self.client_id}",
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('has_request'):
                        token = data['token']
                        sender_id = data['sender_id']
                        metadata = data['metadata']
                        
                        if self.transfer_callback:
                            self.transfer_callback(token, sender_id, metadata)
                
            except Exception as e:
                # Long-polling timeout is expected
                if "timeout" not in str(e).lower():
                    print(f"⚠ Poll error: {e}")
            
            time.sleep(0.5)  # Brief pause before next poll
    
    def accept_transfer(self, token: str) -> bool:
        """
        Accept an incoming transfer request.
        
        Args:
            token: Transfer token
            
        Returns:
            bool: True if acceptance successful
        """
        try:
            response = requests.post(
                f"{SERVER_URL}/accept_transfer/{token}",
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✓ Transfer accepted: {token}")
                return True
            else:
                error = response.json().get('error', 'Unknown error')
                print(f"✗ Accept failed: {error}")
                return False
                
        except Exception as e:
            print(f"✗ Accept error: {e}")
            return False
    
    def reject_transfer(self, token: str) -> bool:
        """
        Reject an incoming transfer request.
        
        Args:
            token: Transfer token
            
        Returns:
            bool: True if rejection successful
        """
        try:
            response = requests.post(
                f"{SERVER_URL}/reject_transfer/{token}",
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✓ Transfer rejected: {token}")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"✗ Reject error: {e}")
            return False


import os  # Import at module level for upload_file function

