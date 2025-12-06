"""
Client-side cryptography module for Quantum-Safe File Sharing.
Handles ML-KEM-768 key generation and AES-256-GCM encryption/decryption.
"""

import os
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Try to import oqs for post-quantum cryptography
# If not available, will use standard secure random generation
try:
    import oqs
    HAS_PQC = True
except ImportError:
    HAS_PQC = False
    print("⚠ Warning: liboqs not available")

CHUNK_SIZE = 64 * 1024  # 64 KB chunks


class QuantumSafeCrypto:
    """Handles quantum-safe cryptography operations."""
    
    def __init__(self):
        """Initialize the crypto handler."""
        self.kem_algorithm = "ML-KEM-768" if HAS_PQC else None  # Post-quantum KEM
        if not HAS_PQC:
            print("  ℹ Using secure random keys")
        
    def generate_symmetric_key(self) -> tuple[bytes, bytes]:
        """
        Generate a symmetric key and IV for AES-256-GCM encryption.
        
        Returns:
            tuple: (32-byte AES key, 12-byte nonce/IV)
        """
        # Generate 256-bit (32 bytes) key for AES-256
        aes_key = os.urandom(32)
        
        # Generate 96-bit (12 bytes) nonce for GCM
        nonce = os.urandom(12)
        
        return aes_key, nonce
    
    def generate_kem_keypair(self) -> tuple[bytes, bytes]:
        """
        Generate a post-quantum key pair using ML-KEM-768 (if available).
        
        Returns:
            tuple: (public_key, secret_key)
        """
        if not HAS_PQC:
            raise RuntimeError("Post-quantum cryptography not available. Install liboqs-python.")
        
        kem = oqs.KeyEncapsulation(self.kem_algorithm)
        public_key = kem.generate_keypair()
        secret_key = kem.export_secret_key()
        
        return public_key, secret_key
    
    def encapsulate_key(self, public_key: bytes) -> tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using recipient's public key (if PQC available).
        
        Args:
            public_key: Recipient's ML-KEM-768 public key
            
        Returns:
            tuple: (ciphertext, shared_secret)
        """
        if not HAS_PQC:
            raise RuntimeError("Post-quantum cryptography not available. Install liboqs-python.")
        
        kem = oqs.KeyEncapsulation(self.kem_algorithm)
        ciphertext, shared_secret = kem.encap_secret(public_key)
        
        return ciphertext, shared_secret
    
    def decapsulate_key(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """
        Decapsulate the shared secret using own secret key (if PQC available).
        
        Args:
            ciphertext: Encapsulated key from sender
            secret_key: Own ML-KEM-768 secret key
            
        Returns:
            bytes: Shared secret
        """
        if not HAS_PQC:
            raise RuntimeError("Post-quantum cryptography not available. Install liboqs-python.")
        
        kem = oqs.KeyEncapsulation(self.kem_algorithm, secret_key=secret_key)
        shared_secret = kem.decap_secret(ciphertext)
        
        return shared_secret
    
    def compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hex-encoded SHA-256 hash
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def encrypt_file(self, input_path: str, output_path: str, key: bytes, nonce: bytes) -> dict:
        """
        Encrypt a file using AES-256-GCM.
        
        Args:
            input_path: Path to plaintext file
            output_path: Path to save encrypted file
            key: 32-byte AES key
            nonce: 12-byte nonce
            
        Returns:
            dict: Metadata including file hash and size
        """
        # Compute hash of plaintext file
        file_hash = self.compute_file_hash(input_path)
        
        # Initialize AES-GCM cipher
        aesgcm = AESGCM(key)
        
        # Get file size
        file_size = os.path.getsize(input_path)
        
        with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
            # Write nonce first
            fout.write(nonce)
            
            # Write file hash
            fout.write(file_hash.encode('utf-8'))
            fout.write(b'\n')  # Separator
            
            # Encrypt and write file content in chunks
            chunk_counter = 0
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                # Create unique nonce for each chunk by incrementing
                chunk_nonce = int.from_bytes(nonce, 'big') + chunk_counter
                chunk_nonce = chunk_nonce.to_bytes(12, 'big')
                
                # Encrypt chunk (GCM adds 16-byte authentication tag)
                encrypted_chunk = aesgcm.encrypt(chunk_nonce, chunk, None)
                
                # Write chunk size (4 bytes) then encrypted chunk
                chunk_size = len(encrypted_chunk)
                fout.write(chunk_size.to_bytes(4, 'big'))
                fout.write(encrypted_chunk)
                
                chunk_counter += 1
        
        return {
            'file_hash': file_hash,
            'original_size': file_size,
            'encrypted_size': os.path.getsize(output_path)
        }
    
    def decrypt_file(self, input_path: str, output_path: str, key: bytes) -> dict:
        """
        Decrypt a file using AES-256-GCM and verify integrity.
        
        Args:
            input_path: Path to encrypted file
            output_path: Path to save decrypted file
            key: 32-byte AES key
            
        Returns:
            dict: Metadata including hash verification result
        """
        aesgcm = AESGCM(key)
        
        with open(input_path, 'rb') as fin, open(output_path, 'wb') as fout:
            # Read base nonce (12 bytes)
            base_nonce = fin.read(12)
            
            # Read original file hash
            hash_line = b''
            while True:
                byte = fin.read(1)
                if byte == b'\n':
                    break
                hash_line += byte
            
            original_hash = hash_line.decode('utf-8')
            
            # Decrypt chunks
            chunk_counter = 0
            while True:
                # Read chunk size
                size_bytes = fin.read(4)
                if not size_bytes or len(size_bytes) < 4:
                    break
                
                chunk_size = int.from_bytes(size_bytes, 'big')
                
                # Read encrypted chunk
                encrypted_chunk = fin.read(chunk_size)
                if not encrypted_chunk:
                    break
                
                # Reconstruct nonce for this chunk
                chunk_nonce = int.from_bytes(base_nonce, 'big') + chunk_counter
                chunk_nonce = chunk_nonce.to_bytes(12, 'big')
                
                # Decrypt chunk
                try:
                    decrypted_chunk = aesgcm.decrypt(chunk_nonce, encrypted_chunk, None)
                    fout.write(decrypted_chunk)
                except Exception as e:
                    raise ValueError(f"Decryption failed: {e}")
                
                chunk_counter += 1
        
        # Verify file hash
        decrypted_hash = self.compute_file_hash(output_path)
        hash_valid = (decrypted_hash == original_hash)
        
        return {
            'original_hash': original_hash,
            'decrypted_hash': decrypted_hash,
            'hash_valid': hash_valid,
            'file_size': os.path.getsize(output_path)
        }
    
    def create_sk_bundle(self, key: bytes, nonce: bytes, file_hash: str) -> str:
        """
        Create a Symmetric Key Bundle for transmission.
        This would normally be encrypted with the recipient's public key,
        but for the prototype, we'll use base64 encoding as per the out-of-band
        exchange simulation.
        
        Args:
            key: AES-256 key
            nonce: 12-byte nonce
            file_hash: SHA-256 hash of the file
            
        Returns:
            str: Base64-encoded SK bundle
        """
        bundle = {
            'key': base64.b64encode(key).decode('utf-8'),
            'nonce': base64.b64encode(nonce).decode('utf-8'),
            'hash': file_hash
        }
        
        # In a real implementation, this would be encrypted with recipient's public key
        # For prototype, we'll just JSON-encode and base64 it
        import json
        bundle_json = json.dumps(bundle)
        bundle_b64 = base64.b64encode(bundle_json.encode('utf-8')).decode('utf-8')
        
        return bundle_b64
    
    def parse_sk_bundle(self, bundle_b64: str) -> dict:
        """
        Parse a Symmetric Key Bundle.
        
        Args:
            bundle_b64: Base64-encoded SK bundle
            
        Returns:
            dict: Parsed bundle with key, nonce, hash
        """
        import json
        
        # Decode base64
        bundle_json = base64.b64decode(bundle_b64).decode('utf-8')
        bundle = json.loads(bundle_json)
        
        # Decode key and nonce from base64
        key = base64.b64decode(bundle['key'])
        nonce = base64.b64decode(bundle['nonce'])
        file_hash = bundle['hash']
        
        return {
            'key': key,
            'nonce': nonce,
            'hash': file_hash
        }


def derive_key_from_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """
    Derive a key from a password using PBKDF2.
    Useful for password-based encryption (optional feature).
    
    Args:
        password: User password
        salt: Salt for key derivation (generated if None)
        
    Returns:
        tuple: (derived_key, salt)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = kdf.derive(password.encode('utf-8'))
    
    return key, salt

