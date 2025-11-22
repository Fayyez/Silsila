"""
Flask web application for Quantum-Safe File Sharing client.
Provides a modern web interface for secure file transfers.
"""

from flask import Flask, render_template, request, jsonify, send_file
import os
import threading
import tempfile
import time
from werkzeug.utils import secure_filename
from modules import QuantumSafeCrypto, ServerClient

app = Flask(__name__, template_folder='pages')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max

# Global state
crypto = QuantumSafeCrypto()
server_client = None
client_id = None
temp_dir = tempfile.mkdtemp()
downloads_dir = os.path.join(os.getcwd(), 'client', 'downloads')

# Storage for active transfers
pending_transfers = {}  # token -> transfer_data
active_uploads = {}  # token -> progress_data
active_downloads = {}  # token -> progress_data

# Ensure downloads directory exists
os.makedirs(downloads_dir, exist_ok=True)


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('home.html')


@app.route('/api/register', methods=['POST'])
def register_client():
    """Register this client with the server."""
    global server_client, client_id
    
    data = request.get_json()
    client_id = data.get('client_id')
    
    if not client_id:
        return jsonify({'error': 'Client ID required'}), 400
    
    # Create server client
    server_client = ServerClient(client_id)
    
    # Register with server
    if server_client.register():
        # Start heartbeat
        server_client.start_heartbeat()
        
        # Start listening for transfers
        server_client.start_listening(handle_incoming_transfer)
        
        return jsonify({
            'success': True,
            'client_id': client_id,
            'message': 'Connected to server'
        }), 200
    else:
        return jsonify({'error': 'Registration failed'}), 500


@app.route('/api/clients', methods=['GET'])
def get_clients():
    """Get list of online clients."""
    if not server_client:
        return jsonify({'error': 'Not registered'}), 400
    
    clients = server_client.get_online_clients()
    return jsonify({'clients': clients}), 200


@app.route('/api/send', methods=['POST'])
def send_file():
    """Initiate file send process."""
    if not server_client:
        return jsonify({'error': 'Not registered'}), 400
    
    # Get uploaded file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    recipient_id = request.form.get('recipient_id')
    
    if not recipient_id:
        return jsonify({'error': 'Recipient ID required'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save uploaded file temporarily
    filename = secure_filename(file.filename)
    temp_input = os.path.join(temp_dir, f"upload_{time.time()}_{filename}")
    file.save(temp_input)
    
    # Start encryption and upload in background thread
    thread = threading.Thread(
        target=process_send_file,
        args=(temp_input, filename, recipient_id),
        daemon=True
    )
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'File upload started',
        'filename': filename
    }), 200


def process_send_file(file_path: str, original_filename: str, recipient_id: str):
    """Process file encryption and upload (runs in background)."""
    try:
        # Generate encryption key
        aes_key, nonce = crypto.generate_symmetric_key()
        
        # Encrypt file
        encrypted_path = file_path + '.enc'
        metadata = crypto.encrypt_file(file_path, encrypted_path, aes_key, nonce)
        
        # Create SK bundle
        sk_bundle = crypto.create_sk_bundle(aes_key, nonce, metadata['file_hash'])
        
        # Request transfer from server
        transfer_metadata = {
            'filename': original_filename,
            'filesize': metadata['encrypted_size'],
            'file_hash': metadata['file_hash'],
            'sk_bundle': sk_bundle
        }
        
        token = server_client.request_transfer(recipient_id, transfer_metadata)
        
        if not token:
            print(f"✗ Failed to request transfer for {original_filename}")
            return
        
        print(f"✓ Transfer requested: {token}")
        print(f"  Waiting for {recipient_id} to accept...")
        
        # Wait for acceptance
        if not server_client.wait_for_acceptance(token, timeout=120):
            print(f"✗ Transfer not accepted: {original_filename}")
            os.remove(file_path)
            os.remove(encrypted_path)
            return
        
        print(f"✓ Transfer accepted! Uploading...")
        
        # Upload file
        def progress_callback(bytes_sent, total_bytes):
            progress = int((bytes_sent / total_bytes) * 100) if total_bytes > 0 else 0
            active_uploads[token] = {
                'filename': original_filename,
                'bytes_sent': bytes_sent,
                'total_bytes': total_bytes,
                'progress': progress
            }
        
        active_uploads[token] = {
            'filename': original_filename,
            'bytes_sent': 0,
            'total_bytes': metadata['encrypted_size'],
            'progress': 0
        }
        
        success = server_client.upload_file(encrypted_path, token, progress_callback)
        
        # Cleanup
        os.remove(file_path)
        os.remove(encrypted_path)
        
        if token in active_uploads:
            del active_uploads[token]
        
        if success:
            print(f"✓ Transfer complete: {original_filename}")
        else:
            print(f"✗ Transfer failed: {original_filename}")
            
    except Exception as e:
        print(f"✗ Error processing send: {e}")


def handle_incoming_transfer(token: str, sender_id: str, metadata: dict):
    """Handle incoming transfer request (called by server_client)."""
    print(f"\n📥 Incoming file from {sender_id}: {metadata.get('filename')}")
    
    # Store pending transfer
    pending_transfers[token] = {
        'token': token,
        'sender_id': sender_id,
        'filename': metadata.get('filename'),
        'filesize': metadata.get('filesize'),
        'file_hash': metadata.get('file_hash'),
        'sk_bundle': metadata.get('sk_bundle'),
        'timestamp': time.time()
    }


@app.route('/api/pending', methods=['GET'])
def get_pending_transfers():
    """Get list of pending incoming transfers."""
    return jsonify({
        'transfers': list(pending_transfers.values())
    }), 200


@app.route('/api/accept', methods=['POST'])
def accept_transfer():
    """Accept an incoming transfer."""
    data = request.get_json()
    token = data.get('token')
    download_path = data.get('download_path', downloads_dir)
    
    if not token or token not in pending_transfers:
        return jsonify({'error': 'Invalid token'}), 400
    
    transfer_data = pending_transfers[token]
    
    # Start download in background
    thread = threading.Thread(
        target=process_receive_file,
        args=(token, transfer_data, download_path),
        daemon=True
    )
    thread.start()
    
    # Remove from pending
    del pending_transfers[token]
    
    return jsonify({
        'success': True,
        'message': 'Download started'
    }), 200


@app.route('/api/reject', methods=['POST'])
def reject_transfer():
    """Reject an incoming transfer."""
    data = request.get_json()
    token = data.get('token')
    
    if not token or token not in pending_transfers:
        return jsonify({'error': 'Invalid token'}), 400
    
    # Reject transfer
    server_client.reject_transfer(token)
    
    # Remove from pending
    del pending_transfers[token]
    
    return jsonify({
        'success': True,
        'message': 'Transfer rejected'
    }), 200


def process_receive_file(token: str, transfer_data: dict, download_path: str):
    """Process file download and decryption (runs in background)."""
    try:
        # Accept transfer on server
        if not server_client.accept_transfer(token):
            print(f"✗ Failed to accept transfer: {token}")
            return
        
        filename = transfer_data['filename']
        sk_bundle = transfer_data['sk_bundle']
        
        print(f"✓ Downloading: {filename}")
        
        # Download encrypted file
        encrypted_path = os.path.join(temp_dir, f"download_{token}.enc")
        
        def progress_callback(bytes_received, total_bytes):
            progress = int((bytes_received / total_bytes) * 100) if total_bytes > 0 else 0
            active_downloads[token] = {
                'filename': filename,
                'bytes_received': bytes_received,
                'total_bytes': total_bytes,
                'progress': progress,
                'status': 'downloading'
            }
        
        active_downloads[token] = {
            'filename': filename,
            'bytes_received': 0,
            'total_bytes': transfer_data['filesize'],
            'progress': 0,
            'status': 'downloading'
        }
        
        if not server_client.download_file(encrypted_path, token, progress_callback):
            print(f"✗ Download failed: {filename}")
            if token in active_downloads:
                del active_downloads[token]
            return
        
        # Parse SK bundle
        bundle = crypto.parse_sk_bundle(sk_bundle)
        key = bundle['key']
        
        # Decrypt file
        active_downloads[token]['status'] = 'decrypting'
        
        # Ensure download directory exists
        os.makedirs(download_path, exist_ok=True)
        
        output_path = os.path.join(download_path, filename)
        
        # Handle duplicate filenames
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(output_path):
            output_path = os.path.join(download_path, f"{base_name}_{counter}{ext}")
            counter += 1
        
        result = crypto.decrypt_file(encrypted_path, output_path, key)
        
        # Cleanup encrypted file
        os.remove(encrypted_path)
        
        if result['hash_valid']:
            print(f"✓ File received and verified: {output_path}")
            print(f"  Hash: {result['decrypted_hash'][:16]}...")
        else:
            print(f"⚠ File received but hash mismatch!")
            print(f"  Expected: {result['original_hash'][:16]}...")
            print(f"  Got:      {result['decrypted_hash'][:16]}...")
        
        # Update status
        if token in active_downloads:
            active_downloads[token]['status'] = 'complete'
            active_downloads[token]['output_path'] = output_path
            active_downloads[token]['hash_valid'] = result['hash_valid']
            
            # Remove after a delay
            def cleanup():
                time.sleep(5)
                if token in active_downloads:
                    del active_downloads[token]
            
            threading.Thread(target=cleanup, daemon=True).start()
        
    except Exception as e:
        print(f"✗ Error receiving file: {e}")
        if token in active_downloads:
            active_downloads[token]['status'] = 'error'
            active_downloads[token]['error'] = str(e)


@app.route('/api/uploads/status', methods=['GET'])
def get_upload_status():
    """Get status of active uploads."""
    return jsonify({
        'uploads': list(active_uploads.values())
    }), 200


@app.route('/api/downloads/status', methods=['GET'])
def get_download_status():
    """Get status of active downloads."""
    return jsonify({
        'downloads': list(active_downloads.values())
    }), 200


@app.route('/api/status', methods=['GET'])
def get_client_status():
    """Get overall client status."""
    return jsonify({
        'registered': server_client is not None,
        'client_id': client_id,
        'pending_count': len(pending_transfers),
        'active_uploads': len(active_uploads),
        'active_downloads': len(active_downloads)
    }), 200


if __name__ == '__main__':
    import sys
    
    # Allow port to be specified via command line
    port = 5001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except:
            pass
    
    print("=" * 60)
    print("Quantum-Safe File Sharing Client")
    print("=" * 60)
    print(f"Starting client interface on http://127.0.0.1:{port}")
    print(f"Downloads will be saved to: {downloads_dir}")
    print("=" * 60)
    
    # Run Flask app
    app.run(
        host='127.0.0.1',
        port=port,
        debug=False,  # Disable debug mode for cleaner output
        threaded=True
    )

