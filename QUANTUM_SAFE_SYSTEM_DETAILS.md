# Quantum-Safe File Sharing System: Technical Architecture & Working Details

## 1. System Overview

This document details the technical implementation of the "Silsila" Quantum-Safe File Sharing System. The system is designed to provide secure, peer-to-peer file transfer capabilities protected by Post-Quantum Cryptography (PQC), specifically aiming to resist attacks from future quantum computers while maintaining compatibility with current classical systems.

The architecture follows a **Client-Server model** where:
- **Clients** handle all cryptographic operations (End-to-End Encryption).
- **Server** acts as a signaling relay and temporary data conduit, with zero knowledge of the file contents or encryption keys (Zero-Knowledge Provider).

## 2. Cryptographic Architecture

The core security proposition relies on a hybrid approach combining established symmetric encryption with post-quantum key encapsulation.

### 2.1 Post-Quantum Key Encapsulation (PQC)
The system is designed to use **ML-KEM-768** (formerly Kyber-768), a NIST-standardized Key Encapsulation Mechanism (KEM).

- **Algorithm**: ML-KEM-768
- **Library**: `liboqs-python` (Python wrapper for Open Quantum Safe's liboqs).
- **Workflow**:
    1.  **Key Generation**: Recipient generates a Key Pair (Public Key `pk`, Secret Key `sk`).
    2.  **Encapsulation**: Sender uses `pk` to encapsulate a shared secret, producing a Ciphertext `ct` and the Shared Secret `ss`.
    3.  **Decapsulation**: Recipient uses `sk` and `ct` to recover the Shared Secret `ss`.
- **Prototype Status**: The code supports `liboqs`, but includes a fallback mechanism for environments where it is not installed (e.g., standard Windows setups). In fallback mode, it simulates the exchange by generating secure random keys directly.

### 2.2 Symmetric Encryption (Payload Protection)
File data is encrypted using **AES-256-GCM** (Galois/Counter Mode), providing both confidentiality and integrity/authenticity.

- **Algorithm**: AES-256-GCM
- **Key Size**: 256 bits (32 bytes)
- **Nonce/IV**: 96 bits (12 bytes)
- **Library**: `cryptography` (Python package)

### 2.3 Key Management & The "SK Bundle"
To facilitate the transfer, a "Symmetric Key Bundle" (SK Bundle) is created by the sender.

**Bundle Contents:**
1.  **Symmetric Key**: The 32-byte AES key.
2.  **Nonce**: The 12-byte initialization vector.
3.  **File Hash**: SHA-256 hash of the original plaintext file.

**Transmission:**
- In the **PQC-enabled flow**, this bundle is serialized and encrypted using the Shared Secret derived from ML-KEM-768.
- In the **Prototype flow**, the bundle is Base64 encoded to simulate the payload structure, assuming an out-of-band secure channel (like Signal or WhatsApp) for the initial key exchange simulation.

## 3. File Transfer Protocol

The system implements a custom HTTP-based protocol for signaling and data streaming.

### 3.1 Signaling & Handshake
Before data transfer, clients perform a handshake via the server.

1.  **Registration**: Clients `POST /register` to announce availability.
2.  **Discovery**: Clients `GET /clients` to find peers.
3.  **Request**: Sender `POST /request_transfer` with recipient ID and file metadata.
    - Server generates a unique `transfer_token`.
4.  **Notification**: Recipient (via Long-Polling on `GET /check_requests`) receives the request.
5.  **Acceptance**: Recipient `POST /accept_transfer/<token>`.

### 3.2 Data Streaming (Chunked Pipeline)
To handle large files without exhausting server RAM, the system uses a streaming conduit pattern.

1.  **Chunking**: The file is read in **64 KB chunks**.
2.  **Encryption Pipeline**:
    - Each chunk is encrypted individually.
    - To ensure security for the stream, the Nonce is **incremented** for each chunk: `Chunk_Nonce = Base_Nonce + Chunk_Index`.
    - Format per chunk: `[Size (4 bytes)] + [Encrypted Data (Size + 16 byte Tag)]`.
3.  **Upload**: Sender `POST /stream_upload/<token>` sends chunks to the server.
4.  **Relay (The Conduit)**:
    - The server holds a small in-memory buffer (Queue).
    - It uses **Condition Variables** to synchronize the Producer (Uploader) and Consumer (Downloader).
    - **Zero-Disk**: Data is never written to the server's hard drive.
5.  **Download**: Recipient `GET /stream_download/<token>` retrieves chunks as they arrive.
6.  **Decryption**: Recipient decrypts chunks on-the-fly, verifies the auth tag, and reconstructs the file.

### 3.3 Integrity Verification
- **Pre-Transfer**: Sender computes SHA-256 of the original file.
- **Post-Transfer**: Recipient computes SHA-256 of the decrypted file.
- **Validation**: The hashes are compared. If they mismatch, the user is warned of potential tampering or corruption.

## 4. Technical Implementation Details

### 4.1 Client Modules
- **`app.py`**: Flask-based web interface acting as the local UI.
- **`modules/crypto_client.py`**:
    - Class `QuantumSafeCrypto`.
    - Handles `oqs` imports and fallbacks.
    - Implements `encrypt_file` and `decrypt_file` with stream processing.
- **`modules/server_client.py`**:
    - Handles HTTP communication with the central server.
    - Implements the Long-Polling loop for real-time notifications.

### 4.2 Server Modules
- **`app.py`**: Entry point and API route definitions.
- **`modules/registry.py`**: Thread-safe dictionary for tracking online clients.
- **`modules/streaming.py`**:
    - Implements the `TransferConduit` class.
    - Manages the in-memory buffer and thread synchronization.
    - Enforces flow control (blocking the uploader if the downloader is slow).

### 4.3 Security Considerations
1.  **Memory Security**: Large files are never loaded entirely into RAM; they are processed in fixed-size blocks.
2.  **Forward Secrecy**: (In full PQC mode) Ephemeral keys generated for each session ensure that compromising long-term keys does not decrypt past sessions.
3.  **Authentication**: The current prototype relies on the GCM Auth Tag for data authenticity. Future versions would include digital signatures (e.g., ML-DSA/Dilithium) for sender identity verification.

## 5. Summary of Technologies

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **PQC KEM** | ML-KEM-768 | Quantum-safe key exchange |
| **Symmetric Cipher** | AES-256-GCM | High-speed data encryption |
| **Hash Function** | SHA-256 | File integrity check |
| **Server Framework** | Flask (Python) | REST API & Signaling |
| **Client UI** | HTML5/JS + Flask | Local user interface |
| **Transport** | HTTP/1.1 | Signaling & Data Stream |


