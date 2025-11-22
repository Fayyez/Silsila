"""
Test script to verify all server endpoints are working correctly.
Run this while the server is running to test functionality.
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"


def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()['status'] == 'healthy'
    print("✓ Health check passed")


def test_server_status():
    """Test status endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: Server Status")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/status")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert data['max_transfers'] == 10
    print("✓ Server status passed")


def test_client_registration():
    """Test client registration"""
    print("\n" + "=" * 60)
    print("TEST 3: Client Registration")
    print("=" * 60)
    
    # Register client 1
    payload = {
        "client_id": "alice",
        "ip_address": "127.0.0.1"
    }
    response = requests.post(f"{BASE_URL}/register", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 201
    print("✓ Client 'alice' registered")
    
    # Register client 2
    payload = {
        "client_id": "bob",
        "ip_address": "127.0.0.1"
    }
    response = requests.post(f"{BASE_URL}/register", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 201
    print("✓ Client 'bob' registered")


def test_heartbeat():
    """Test heartbeat mechanism"""
    print("\n" + "=" * 60)
    print("TEST 4: Heartbeat")
    print("=" * 60)
    
    payload = {"client_id": "alice"}
    response = requests.post(f"{BASE_URL}/heartbeat", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    print("✓ Heartbeat updated")


def test_list_clients():
    """Test listing active clients"""
    print("\n" + "=" * 60)
    print("TEST 5: List Active Clients")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/clients?client_id=alice")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    print(f"✓ Found {data['count']} active client(s)")


def test_transfer_flow():
    """Test complete transfer flow"""
    print("\n" + "=" * 60)
    print("TEST 6: Transfer Flow")
    print("=" * 60)
    
    # Step 1: Request transfer
    print("\n--- Step 1: Request Transfer ---")
    payload = {
        "sender_id": "alice",
        "recipient_id": "bob",
        "metadata": {
            "filename": "test_file.txt",
            "filesize": 1024,
            "file_hash": "abc123def456",
            "sk_bundle": "base64encodedkeydata=="
        }
    }
    response = requests.post(f"{BASE_URL}/request_transfer", json=payload)
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 201
    token = data['token']
    print(f"✓ Transfer request created with token: {token}")
    
    # Step 2: Check status (sender checks if accepted)
    print("\n--- Step 2: Check Transfer Status ---")
    response = requests.get(f"{BASE_URL}/check_status/{token}")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert data['status'] == 'PENDING'
    print("✓ Status is PENDING")
    
    # Step 3: Accept transfer (receiver accepts)
    print("\n--- Step 3: Accept Transfer ---")
    response = requests.post(f"{BASE_URL}/accept_transfer/{token}")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert data['status'] == 'ACCEPTED'
    print("✓ Transfer accepted")
    
    # Step 4: Check status again
    print("\n--- Step 4: Verify Status Changed ---")
    response = requests.get(f"{BASE_URL}/check_status/{token}")
    data = response.json()
    print(f"Status: {data['status']}")
    assert data['status'] == 'ACCEPTED'
    print("✓ Status is ACCEPTED")
    
    # Step 5: Test streaming (upload small test data)
    print("\n--- Step 5: Test Upload Stream ---")
    test_data = b"This is encrypted test data!" * 100  # ~2.8 KB
    response = requests.post(
        f"{BASE_URL}/stream_upload/{token}",
        data=test_data,
        headers={'Content-Type': 'application/octet-stream'}
    )
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    print(f"✓ Uploaded {data['bytes_received']} bytes")
    
    # Step 6: Test download stream
    print("\n--- Step 6: Test Download Stream ---")
    response = requests.get(
        f"{BASE_URL}/stream_download/{token}",
        stream=True
    )
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 200
    
    downloaded_data = b""
    for chunk in response.iter_content(chunk_size=8192):
        downloaded_data += chunk
    
    print(f"Downloaded {len(downloaded_data)} bytes")
    assert downloaded_data == test_data
    print("✓ Data integrity verified (upload == download)")
    
    print("\n✓ Complete transfer flow test passed!")


def test_reject_transfer():
    """Test rejecting a transfer"""
    print("\n" + "=" * 60)
    print("TEST 7: Reject Transfer")
    print("=" * 60)
    
    # Create transfer request
    payload = {
        "sender_id": "alice",
        "recipient_id": "bob",
        "metadata": {
            "filename": "unwanted_file.txt",
            "filesize": 500
        }
    }
    response = requests.post(f"{BASE_URL}/request_transfer", json=payload)
    token = response.json()['token']
    print(f"Transfer token: {token}")
    
    # Reject it
    response = requests.post(f"{BASE_URL}/reject_transfer/{token}")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert data['status'] == 'REJECTED'
    print("✓ Transfer rejected successfully")


def run_all_tests():
    """Run all tests"""
    print("\n")
    print("=" * 60)
    print("QUANTUM-SAFE FILE SHARING SERVER TEST SUITE")
    print("=" * 60)
    
    try:
        test_health()
        test_server_status()
        test_client_registration()
        test_heartbeat()
        test_list_clients()
        test_transfer_flow()
        test_reject_transfer()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
        print("\nServer is working correctly and ready for client implementation.")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Cannot connect to server. Is it running?")
        print("Run: python server/app.py")
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")


if __name__ == "__main__":
    run_all_tests()

