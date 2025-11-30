# Testing Client File Exchange

## Prerequisites

1. Ensure the server is running:
```bash
python server/app.py
```

Server should be running on `http://127.0.0.1:5000`

## Step 1: Create a Test File

Create a simple text file to transfer:

```bash
echo "Hello from Alice! This is a test of quantum-safe file transfer." > test_file.txt
```

## Step 2: Start Client 1 (Alice)

Open a new terminal window and run:

```bash
python client/app.py 5001
```

Then open your browser to: `http://127.0.0.1:5001`

1. Enter client ID: `alice`
2. Click "Connect"

## Step 3: Start Client 2 (Bob)

Open another terminal window and run:

```bash
python client/app.py 5002
```

Then open your browser to: `http://127.0.0.1:5002`

1. Enter client ID: `bob`
2. Click "Connect"

## Step 4: Exchange the File

### On Alice's Browser (http://127.0.0.1:5001):

1. Click the "🔄 Refresh" button to see online clients
2. Select "bob" from the dropdown
3. Click "Choose File" and select `test_file.txt`
4. Click "Send File"
5. Wait for Bob to accept (you'll see upload progress)

### On Bob's Browser (http://127.0.0.1:5002):

1. You should see an incoming file notification appear
2. The file will show: `test_file.txt from alice`
3. (Optional) Click "📁 Choose Location" to specify download path
4. Click "Accept" to receive the file
5. Watch the download progress
6. File will be saved to `client/downloads/test_file.txt` (or your custom path)

## Step 5: Verify the Transfer

Check that the file was received correctly:

```bash
cat client/downloads/test_file.txt
```

You should see:
```
Hello from Alice! This is a test of quantum-safe file transfer.
```

The file has been:
1. ✅ Encrypted with AES-256-GCM
2. ✅ Transmitted through the server's in-memory conduit
3. ✅ Decrypted on the receiver's side
4. ✅ Hash verified for integrity

## What's Happening Under the Hood

1. **Alice's Side:**
   - Generates AES-256 key and nonce
   - Encrypts the file using AES-256-GCM
   - Computes SHA-256 hash of original file
   - Creates SK Bundle (key + nonce + hash)
   - Requests transfer from server with metadata
   - Waits for Bob to accept
   - Streams encrypted chunks (64 KB) to server

2. **Server:**
   - Creates transfer token
   - Signals Bob via long-polling
   - Creates in-memory streaming conduit
   - Relays encrypted chunks from Alice to Bob
   - Never stores data on disk
   - Automatically cleans up after transfer

3. **Bob's Side:**
   - Receives notification via long-polling
   - Displays pending transfer
   - Accepts transfer
   - Streams encrypted chunks from server
   - Parses SK Bundle to get decryption key
   - Decrypts file using AES-256-GCM
   - Verifies SHA-256 hash matches
   - Saves decrypted file to downloads folder

## Testing Different Scenarios

### Test Large Files

Create a larger test file:
```bash
# Create a 10 MB test file
python -c "with open('large_test.txt', 'w') as f: f.write('X' * (10 * 1024 * 1024))"
```

Send this through the clients to test progress bars and chunked transfer.

### Test Multiple Transfers

With both clients still connected:
1. Send another file from Alice to Bob
2. Send a file from Bob to Alice
3. Both can happen simultaneously (up to 10 concurrent transfers)

### Test Rejection

1. Alice sends a file to Bob
2. Bob clicks "Reject" instead of "Accept"
3. Alice will be notified that the transfer was rejected

### Test with 3 Clients

Start a third client:
```bash
python client/app.py 5003
```

Connect as "charlie" and exchange files between all three clients.

## Cleanup

When done testing:

1. Close all browser windows
2. Press `Ctrl+C` in each terminal to stop the clients
3. Press `Ctrl+C` in the server terminal to stop the server
4. Optionally delete test files:
```bash
rm test_file.txt large_test.txt
rm -rf client/downloads/*
```

## Troubleshooting

### "No clients online"
- Make sure both clients are connected
- Click the Refresh button
- Check that heartbeats are being sent (look at server logs)

### Upload/Download stuck
- Check server is still running
- Look at terminal output for error messages
- Check that port 5000 (server) is not blocked

### File not found after download
- Check `client/downloads/` directory
- Look at terminal output for the actual save path
- Verify no errors during decryption

### Hash verification failed
- This indicates data corruption
- Check server logs for errors
- Ensure no interruption during transfer

## Success Indicators

✅ In the terminal, you should see:
- `✓ Registered as 'alice'` (or bob)
- `✓ Heartbeat started`
- `✓ Listening for incoming transfers`
- `✓ Transfer requested: [token]`
- `✓ Transfer accepted! Uploading...`
- `✓ Upload complete: [bytes]`
- `✓ Downloading: [filename]`
- `✓ File received and verified: [path]`

✅ In the browser, you should see:
- Connected status badge
- Online clients in dropdown
- Progress bars during transfer
- Success notifications

✅ In the server logs, you should see:
- Client registrations
- Transfer request created
- Transfer accepted
- Upload/Download complete
- Conduit cleaned up

