# Project Plan: Quantum-Safe File Sharing Service Prototype

## Project Overview
This project aims to build a secure desktop file-sharing system using **Post-Quantum Cryptography (PQC)**. The system utilizes a central server for signaling and relaying data streams between clients, while end-to-end encryption is handled using a hybrid approach (PQC for key encapsulation/derivation, AES-256-GCM for payload encryption).

## Technical Stack
* **Language:** Python 3.x
* **Cryptography:** `liboqs-python` (pyoqs), `cryptography` (AES-GCM)
* **Networking:** HTTP/1.1 (REST API), Long-polling
* **Interface:** Command Line Interface (CLI)

---

## Phase 1: Core Cryptography & Client Logic
**Objective:** Implement the security layer and the client-side protocol state machine.



### 1.1 Symmetric PQC Key Management
- [ ] **Key Generation:** Implement a script/function using `ML-KEM-768` (via `pyoqs`) to generate a high-entropy Symmetric Key (SK) and Initialization Vector (IV).
- [ ] **Static Exchange:** Save keys to a local file (Simulating out-of-band exchange via WhatsApp as per scope).

### 1.2 File Encryption Module (`client/crypto_client.py`)
- [ ] **Integrity Check:** Implement SHA-256 hashing of the plaintext file before encryption.
- [ ] **Encryption:** Implement AES-256-GCM encryption.
    - [ ] Must handle file reading in **chunks** (no loading entire files to RAM).
- [ ] **Packaging:** Create the "Symmetric Key Bundle" (IV + File Hash + Encrypted Data).

### 1.3 Client Protocol Logic (Sender)
- [ ] Implement `POST /request_transfer` logic (Wait for ACCEPTED status).
- [ ] Implement `POST /stream_upload/<token>` logic (Chunked upload).

### 1.4 Client Protocol Logic (Receiver)
- [ ] Implement Long-polling listener.
- [ ] Implement `POST /accept_transfer/<token>`.
- [ ] Implement `GET /stream_download/<token>` (Decrypt chunks on the fly).
- [ ] **Verification:** Compare decrypted file hash against the original SHA-256 hash.
- [ ] **Cleanup:** Send `DELETE /delete/<token>`.

---

## Phase 2: Server Registry & Signaling
**Objective:** Build the server backbone to track users and manage transfer handshakes.



[Image of client-server file transfer architecture diagram]


### 2.1 Client Registration
- [ ] **Endpoint:** `POST /register`
    - [ ] Accept `client_id` and `ip_address`.
    - [ ] Store in in-memory registry `registry.register_client`.
    - [ ] Validation: Return 400 if data missing; 201 if created.

### 2.2 Heartbeat Mechanism
- [ ] **Endpoint:** `POST /heartbeat`
    - [ ] Update `last_seen` timestamp via `registry.update_heartbeat`.
    - [ ] Return 404 if client not found.

### 2.3 Active Client Discovery
- [ ] **Endpoint:** `GET /clients`
    - [ ] Filter clients based on `MAX_CLIENT_LIFETIME_SECONDS`.
    - [ ] Exclude the requester's own ID from the list.

### 2.4 Transfer Handshake (Signaling)
- [ ] **Endpoint:** `POST /request_transfer`
    - [ ] Validate sender/recipient IDs.
    - [ ] Generate unique **Transfer Token**.
    - [ ] Trigger notification state.
- [ ] **Endpoint:** `GET /check_requests/<client_id>` (Long-Polling)
    - [ ] Implement 10-second timeout loop.
    - [ ] Return 200 with metadata if request found; 204 if timeout.
- [ ] **Endpoints:** `POST /accept_transfer` & `POST /reject_transfer`
    - [ ] Update status to 'ACCEPTED' or 'REJECTED'.
    - [ ] Initialize streaming buffers if Accepted.

---

## Phase 3: Streaming Infrastructure (Server)
**Objective:** Implement the in-memory data conduit to pipe data from Sender to Receiver without disk storage on the server.

### 3.1 Upload Stream
- [ ] **Endpoint:** `POST /stream_upload/<token>`
    - [ ] Verify token is 'ACCEPTED'.
    - [ ] Read request body in chunks.
    - [ ] Write to in-memory buffer (Conduit).
    - [ ] Notify Condition Variable (Producer logic).
    - [ ] Set `transfer_complete` flag upon finish.

### 3.2 Download Stream
- [ ] **Endpoint:** `GET /stream_download/<token>`
    - [ ] Verify token is 'ACCEPTED'.
    - [ ] Implement generator function `generate_chunks`.
    - [ ] Wait on Condition Variable if buffer empty (Consumer logic).
    - [ ] Yield data chunks to receiver.
    - [ ] Cleanup: Remove from `TRANSFER_CONDUITS` upon completion.

---

## Phase 4: User Interface (CLI) & Integration
**Objective:** Create the user-facing application to drive the logic.

### 4.1 Startup & Menu
- [ ] **Startup:** Prompt for `Client ID` -> Auto-call `POST /register`.
- [ ] **Main Menu:**
    - [ ] Loop `GET /clients` to show online users.
    - [ ] Options: [1] Refresh List, [2] Send File, [3] Wait for Transfer.

### 4.2 Sender Experience
- [ ] Input: File Path & Recipient ID.
- [ ] UI: Display "Waiting for acceptance...".
- [ ] UI: Progress bar during `stream_upload`.

### 4.3 Receiver Experience
- [ ] Background Thread: Run `GET /check_requests` loop.
- [ ] Notification: "Incoming file from [ID]. Accept [Y/N]?".
- [ ] UI: Progress bar during `stream_download`.

### 4.4 Error Handling
- [ ] Add `try/except` blocks for network timeouts.
- [ ] Ensure graceful exit (Ctrl+C) deregisters the client.