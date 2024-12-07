import sqlite3
from flask import Flask, request, jsonify
import hashlib
import random
import time

app = Flask(__name__)

# Dictionary to store peer information: {info_hash: {peer_id: peer_data}}
peer_db = {}

# # Helper function to generate peer ID
# def generate_peer_id(peer_ip,peer_port):
#     return f"peer_{peer_ip}_{peer_port}"

# # Helper function to generate info_hash from a torrent file (for simplicity, we use random)
# def generate_info_hash():
#     return hashlib.sha1(str(time.time()).encode('utf-8')).hexdigest()

# Initialize SQLite Database
def init_db():
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    # Create table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS peers (
                    info_hash TEXT,
                    peer_id TEXT,
                    ip TEXT,
                    port INTEGER,
                    downloaded INTEGER,
                    left INTEGER,
                    last_seen REAL)''')
    conn.commit()
    conn.close()

# Insert or update peer in the database
def upsert_peer(info_hash, peer_id, ip, port, downloaded, left):
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO peers (info_hash, peer_id, ip, port, downloaded, left, last_seen)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (info_hash, peer_id, ip, port, downloaded, left, time.time()))
    conn.commit()
    conn.close()

# Get peer list for a specific torrent (info_hash)
def get_peer_list(info_hash):
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    c.execute("SELECT peer_id, ip, port FROM peers WHERE info_hash=?", (info_hash,))
    peers = c.fetchall()
    conn.close()
    return [{"peer_id": peer[0], "ip": peer[1], "port": peer[2]} for peer in peers]

# Announce endpoint for peer communication with the tracker
@app.route('/announce', methods=['GET'])
def announce():
    # Get parameters from the announce request
    info_hash = request.args.get('info_hash')  # Info hash of the torrent
    peer_id = request.args.get('peer_id')  # Peer ID
    port = int(request.args.get('port'))  # Peer listening port
    downloaded = int(request.args.get('downloaded'))  # Amount downloaded by the peer
    left = int(request.args.get('left'))  # Amount left to download
    event = request.args.get('event', '')  # Event type: 'started', 'completed', 'stopped'
    compact = request.args.get('compact', '')  # Compact flag for peer list

    # If no info_hash is provided, return error
    if not info_hash:
        return 'Error: Missing info_hash', 400

    # Handle started/completed/stopped events
    if event == 'started' or event == 'completed':
        upsert_peer(info_hash, peer_id, request.remote_addr, port, downloaded, left)

    elif event == 'stopped':
        conn = sqlite3.connect('tracker.db')
        c = conn.cursor()
        c.execute("DELETE FROM peers WHERE info_hash=? AND peer_id=?", (info_hash, peer_id))
        conn.commit()
        conn.close()

    # Get the peer list for this torrent
    peers = get_peer_list(info_hash)

    # Handle compact mode
    if compact:
        peers_data = b''.join([bytes(f"{peer['ip']}:{peer['port']}", 'utf-8') for peer in peers])
        return peers_data

    # Return a JSON response with the peer list
    return jsonify({
        'interval': 1800,  # Time to wait before the peer should announce again
        'tracker_id': 'abcdef12345',  # Track the session ID
        'peers': peers  # List of peers
    })

if __name__ == '__main__':
    init_db()  # Initialize the database
    app.run(debug=True, host='0.0.0.0', port=8080)
