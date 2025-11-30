"""
Flask Server for Quantum-Safe File Sharing Service
Implements signaling, client registry, and in-memory streaming conduits.
"""

from flask import Flask, request, jsonify, Response, stream_with_context
import json
import time
from modules import registry, signaling, streaming

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max file size

# Server Configuration
SERVER_HOST = '127.0.0.1'  # localhost only
SERVER_PORT = 5000


# ============================================================================
# CORS Support
# ============================================================================

@app.before_request
def handle_preflight():
    """Handle CORS preflight requests."""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200


@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses."""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ============================================================================
# Phase 2.1: Client Registration
# ============================================================================

@app.route('/register', methods=['POST'])
def register():
    """
    Registers a client with the server.
    Expected JSON: { "client_id": str, "ip_address": str, "socket_number": str (optional) }
    """
    data = request.get_json()
    
    if not data or 'client_id' not in data or 'ip_address' not in data:
        return jsonify({'error': 'Missing client_id or ip_address'}), 400
    
    client_id = data['client_id']
    ip_address = data['ip_address']
    socket_number = data.get('socket_number')
    
    # If socket_number not provided, try to extract from request
    if not socket_number:
        # Get the remote port from the request
        socket_number = str(request.remote_addr) + ':' + str(request.environ.get('REMOTE_PORT', 'unknown'))
    
    registry.register_client(client_id, ip_address, socket_number)
    
    return jsonify({
        'message': 'Client registered successfully',
        'client_id': client_id,
        'socket_number': socket_number
    }), 201


# ============================================================================
# Phase 2.2: Heartbeat Mechanism
# ============================================================================

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    Updates the client's last_seen timestamp.
    Expected JSON: { "client_id": str }
    """
    data = request.get_json()
    
    if not data or 'client_id' not in data:
        return jsonify({'error': 'Missing client_id'}), 400
    
    client_id = data['client_id']
    
    if registry.update_heartbeat(client_id):
        return jsonify({'message': 'Heartbeat updated'}), 200
    else:
        return jsonify({'error': 'Client not found'}), 404


# ============================================================================
# Phase 2.3: Active Client Discovery
# ============================================================================

@app.route('/clients', methods=['GET'])
def list_clients():
    """
    Returns a list of active clients (excluding the requester).
    Query parameter: client_id (optional, to exclude from list)
    """
    current_client_id = request.args.get('client_id')
    
    active_clients = registry.get_active_clients(current_client_id)
    
    return jsonify({
        'clients': active_clients,
        'count': len(active_clients)
    }), 200


@app.route('/clients_stream', methods=['GET'])
def clients_stream():
    """
    Server-Sent Events endpoint for real-time client list updates.
    Streams updated client list whenever the registry changes.
    """
    current_client_id = request.args.get('client_id')
    print(f"[SSE] Client stream started for: {current_client_id}")
    
    def generate_events():
        """Generator function to stream events."""
        # Subscribe to registry changes
        subscriber_queue = registry.subscribe()
        
        try:
            # Send initial state
            active_clients = registry.get_active_clients(current_client_id)
            print(f"[SSE] Sending initial state to {current_client_id}: {len(active_clients)} clients")
            yield f"data: {json.dumps({'clients': active_clients, 'count': len(active_clients)})}\n\n"
            
            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for update (timeout after 30 seconds to keep connection alive)
                    update = subscriber_queue.get(timeout=30)
                    
                    # Rebuild client list excluding current client
                    active_clients = registry.get_active_clients(current_client_id)
                    print(f"[SSE] Sending update to {current_client_id}: {len(active_clients)} clients")
                    yield f"data: {json.dumps({'clients': active_clients, 'count': len(active_clients)})}\n\n"
                    
                except Exception as e:
                    # Timeout occurred, send keep-alive comment
                    yield ": keep-alive\n\n"
                    
        except GeneratorExit:
            print(f"[SSE] Client stream closed for: {current_client_id}")
        finally:
            # Unsubscribe when connection closes
            registry.unsubscribe(subscriber_queue)
    
    return Response(
        stream_with_context(generate_events()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# ============================================================================
# Phase 2.4: Transfer Handshake (Signaling)
# ============================================================================

@app.route('/request_transfer', methods=['POST'])
def request_transfer():
    """
    Sender initiates a file transfer request.
    Expected JSON: {
        "sender_id": str,
        "recipient_id": str,
        "metadata": {
            "filename": str,
            "filesize": int,
            "file_hash": str,
            "sk_bundle": str (base64 encoded symmetric key bundle)
        }
    }
    Returns: { "token": str }
    """
    data = request.get_json()
    
    if not data or 'sender_id' not in data or 'recipient_id' not in data:
        return jsonify({'error': 'Missing sender_id or recipient_id'}), 400
    
    sender_id = data['sender_id']
    recipient_id = data['recipient_id']
    metadata = data.get('metadata', {})
    
    # Validate that both clients exist and are active
    active_clients = registry.get_active_clients()
    active_client_ids = [c['id'] for c in active_clients]
    
    if sender_id not in active_client_ids and sender_id not in registry.CLIENTS:
        return jsonify({'error': 'Sender not registered'}), 404
    
    if recipient_id not in active_client_ids and recipient_id not in registry.CLIENTS:
        return jsonify({'error': 'Recipient not found or offline'}), 404
    
    # Create transfer request and get token
    transfer_token = signaling.create_transfer_request(sender_id, recipient_id, metadata)
    
    return jsonify({
        'token': transfer_token,
        'message': 'Transfer request created',
        'status': 'PENDING'
    }), 201


@app.route('/check_requests/<client_id>', methods=['GET'])
def check_requests(client_id):
    """
    Long-polling endpoint for receivers to wait for incoming transfer requests.
    Blocks for up to 10 seconds.
    """
    # Validate client exists
    if client_id not in registry.CLIENTS:
        # Don't log 404s here - they're expected when a client re-registers with a new ID
        return jsonify({'error': 'Client not registered'}), 404
    
    # Wait for requests (long-polling with 10 second timeout)
    request_data = signaling.check_for_requests(client_id, timeout=10)
    
    if request_data:
        return jsonify({
            'has_request': True,
            'token': request_data['token'],
            'sender_id': request_data['sender_id'],
            'metadata': request_data['metadata']
        }), 200
    else:
        # Timeout - no requests
        return jsonify({'has_request': False}), 204


@app.route('/accept_transfer/<token>', methods=['POST'])
def accept_transfer(token):
    """
    Receiver accepts the transfer request.
    Initializes the streaming conduit.
    """
    request_data = signaling.get_request_data(token)
    
    if not request_data:
        return jsonify({'error': 'Transfer token not found'}), 404
    
    if request_data['status'] != 'PENDING':
        return jsonify({'error': f'Transfer already {request_data["status"]}'}), 400
    
    # Check if we can handle another transfer
    if not streaming.initialize_conduit(token):
        return jsonify({'error': 'Server at maximum capacity'}), 503
    
    # Update status to ACCEPTED
    signaling.update_request_status(token, 'ACCEPTED')
    
    return jsonify({
        'message': 'Transfer accepted',
        'token': token,
        'status': 'ACCEPTED'
    }), 200


@app.route('/reject_transfer/<token>', methods=['POST'])
def reject_transfer(token):
    """
    Receiver rejects the transfer request.
    """
    request_data = signaling.get_request_data(token)
    
    if not request_data:
        return jsonify({'error': 'Transfer token not found'}), 404
    
    if request_data['status'] != 'PENDING':
        return jsonify({'error': f'Transfer already {request_data["status"]}'}), 400
    
    # Update status to REJECTED
    signaling.update_request_status(token, 'REJECTED')
    
    return jsonify({
        'message': 'Transfer rejected',
        'token': token,
        'status': 'REJECTED'
    }), 200


@app.route('/check_status/<token>', methods=['GET'])
def check_status(token):
    """
    Allows sender to check if receiver has accepted/rejected.
    """
    request_data = signaling.get_request_data(token)
    
    if not request_data:
        return jsonify({'error': 'Transfer token not found'}), 404
    
    return jsonify({
        'token': token,
        'status': request_data['status'],
        'recipient_id': request_data['recipient_id'],
        'sender_id': request_data['sender_id']
    }), 200


# ============================================================================
# Phase 3: Streaming Infrastructure
# ============================================================================

@app.route('/stream_upload/<token>', methods=['POST'])
def stream_upload(token):
    """
    Sender uploads encrypted file chunks.
    Streams data into in-memory buffer.
    """
    # Verify transfer is accepted
    request_data = signaling.get_request_data(token)
    
    if not request_data:
        return jsonify({'error': 'Transfer token not found'}), 404
    
    if request_data['status'] != 'ACCEPTED':
        return jsonify({'error': 'Transfer not accepted yet'}), 400
    
    # Ensure conduit exists
    if token not in streaming.TRANSFER_CONDUITS:
        return jsonify({'error': 'Streaming conduit not initialized'}), 500
    
    try:
        # Read and write chunks from request body
        bytes_received = 0
        chunk_size = streaming.CHUNK_SIZE
        
        while True:
            chunk = request.stream.read(chunk_size)
            if not chunk:
                break
            
            # Write chunk to conduit
            if not streaming.write_chunk(token, chunk):
                return jsonify({'error': 'Failed to write chunk to conduit'}), 500
            
            bytes_received += len(chunk)
        
        # Mark transfer as complete
        streaming.mark_transfer_complete(token)
        
        print(f"[UPLOAD] Completed for token {token}. Total bytes: {bytes_received}")
        
        return jsonify({
            'message': 'Upload complete',
            'bytes_received': bytes_received
        }), 200
        
    except Exception as e:
        print(f"[UPLOAD ERROR] Token {token}: {str(e)}")
        streaming.mark_transfer_error(token, str(e))
        return jsonify({'error': 'Upload failed', 'details': str(e)}), 500


@app.route('/stream_download/<token>', methods=['GET'])
def stream_download(token):
    """
    Receiver downloads encrypted file chunks.
    Streams data from in-memory buffer.
    """
    # Verify transfer is accepted
    request_data = signaling.get_request_data(token)
    
    if not request_data:
        return jsonify({'error': 'Transfer token not found'}), 404
    
    if request_data['status'] != 'ACCEPTED':
        return jsonify({'error': 'Transfer not accepted'}), 400
    
    # Ensure conduit exists
    if token not in streaming.TRANSFER_CONDUITS:
        return jsonify({'error': 'Streaming conduit not initialized'}), 500
    
    def generate_chunks():
        """Generator function to stream chunks to receiver."""
        try:
            bytes_sent = 0
            
            while True:
                chunk = streaming.read_chunk(token, timeout=30.0)
                
                if chunk is None:
                    # Transfer complete or error
                    break
                
                bytes_sent += len(chunk)
                yield chunk
            
            print(f"[DOWNLOAD] Completed for token {token}. Total bytes: {bytes_sent}")
            
        except Exception as e:
            print(f"[DOWNLOAD ERROR] Token {token}: {str(e)}")
            streaming.mark_transfer_error(token, str(e))
        
        finally:
            # Cleanup after download complete
            streaming.cleanup_conduit(token)
            signaling.delete_request(token)
    
    return Response(
        stream_with_context(generate_chunks()),
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename="transfer_{token}.enc"',
            'X-Transfer-Token': token
        }
    )


@app.route('/delete/<token>', methods=['DELETE'])
def delete_transfer(token):
    """
    Cleanup endpoint to remove transfer data after completion.
    """
    conduit_deleted = streaming.cleanup_conduit(token)
    request_deleted = signaling.delete_request(token)
    
    if conduit_deleted or request_deleted:
        return jsonify({'message': 'Transfer data deleted'}), 200
    else:
        return jsonify({'error': 'Transfer not found'}), 404


# ============================================================================
# Utility Endpoints
# ============================================================================

@app.route('/status', methods=['GET'])
def server_status():
    """
    Returns server status and statistics.
    """
    return jsonify({
        'status': 'online',
        'active_clients': len(registry.CLIENTS),
        'active_transfers': streaming.get_active_transfer_count(),
        'max_transfers': streaming.MAX_CONCURRENT_TRANSFERS,
        'pending_requests': len(signaling.TRANSFER_REQUESTS)
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return jsonify({'status': 'healthy'}), 200


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large'}), 413


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Quantum-Safe File Sharing Server")
    print("=" * 60)
    print(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    print(f"Max concurrent transfers: {streaming.MAX_CONCURRENT_TRANSFERS}")
    print(f"Chunk size: {streaming.CHUNK_SIZE} bytes")
    print("=" * 60)
    
    # Run Flask app
    app.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        debug=True,
        threaded=True  # Enable threading for concurrent requests
    )
