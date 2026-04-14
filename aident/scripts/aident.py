#!/usr/bin/env python3
"""Register an agent on AIdent.store — identity, heartbeat, and metadata."""

import json, subprocess, sys, os, time, hashlib, base64
from pathlib import Path

API_BASE = "https://api.aident.store"

def api(method, path, body=None, headers=None):
    cmd = ['curl', '-s', '-X', method, f'{API_BASE}{path}',
           '-H', 'Content-Type: application/json']
    if headers:
        for k, v in headers.items():
            cmd += ['-H', f'{k}: {v}']
    if body:
        cmd += ['-d', json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(r.stdout)
    except:
        return {"raw": r.stdout, "status": "parse_error"}

def generate_keypair():
    """Generate Ed25519 keypair using pynacl. Returns (seed_b64, public_b64)."""
    try:
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        # Store the 32-byte seed (can reconstruct signing key from it)
        seed_b64 = base64.b64encode(bytes(sk)).decode()
        pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()
        return seed_b64, pub_b64
    except ImportError:
        print("ERROR: pynacl is required. Install with: pip install pynacl")
        sys.exit(1)

def sign_message(privkey_b64, message):
    """Sign a message with Ed25519 private key using pynacl."""
    from nacl.signing import SigningKey
    seed = base64.b64decode(privkey_b64)
    sk = SigningKey(seed)
    signed = sk.sign(message.encode())
    return base64.b64encode(signed.signature).decode()

def register(name, description=None, creator=None):
    """Register a new agent on AIdent.store."""
    priv, pub = generate_keypair()
    if not pub:
        print("ERROR: Failed to generate keypair. Make sure openssl supports Ed25519.")
        sys.exit(1)
    
    body = {"name": name, "public_key": pub}
    if description:
        body["description"] = description
    if creator:
        body["creator"] = creator
    
    result = api("POST", "/v1/register", body)
    if "error" in result:
        print(f"Registration failed: {result['error']}")
        sys.exit(1)
    
    uid = result.get("uid", "")
    print(f"Registered successfully!")
    print(f"  UID: {uid}")
    
    # Save to OpenClaw workspace by default, or --dir if specified
    output_dir = Path(os.environ.get("OPENCLAW_WORKSPACE", Path.cwd()))
    key_path = output_dir / "aident_privkey.b64"
    uid_path = output_dir / "aident_uid.txt"
    
    if key_path.exists():
        print(f"WARNING: {key_path} already exists. Not overwriting.")
    else:
        key_path.write_text(priv)
        key_path.chmod(0o600)
        print(f"  Private key saved to: {key_path} (permissions: 600)")
    
    uid_path.write_text(uid)
    uid_path.chmod(0o644)
    print(f"  UID saved to: {uid_path}")
    
    return uid, priv

def heartbeat(uid, privkey_b64):
    """Send a heartbeat to prove liveness."""
    ts = str(int(time.time() * 1000))
    path = "/v1/heartbeat"
    method = "POST"
    body_str = ""
    sha = hashlib.sha256(body_str.encode()).hexdigest()
    msg = f"{ts}:{uid}:{method}:{path}:{sha}"
    sig = sign_message(privkey_b64, msg)
    
    headers = {
        "X-AIdent-UID": uid,
        "X-AIdent-Timestamp": ts,
        "X-AIdent-Signature": sig
    }
    result = api("POST", path, headers=headers)
    if result.get("status") == "alive":
        print(f"Heartbeat sent! Status: alive")
    else:
        print(f"Heartbeat result: {result}")
    return result

def put_meta(uid, privkey_b64, meta_type, content):
    """PUT public or private metadata. meta_type: 'public' or 'private'"""
    ts = str(int(time.time() * 1000))
    path = f"/v1/meta/{uid}/{meta_type}"
    method = "PUT"
    body_obj = {"content": content}
    body_str = json.dumps(body_obj)
    sha = hashlib.sha256(body_str.encode()).hexdigest()
    msg = f"{ts}:{uid}:{method}:{path}:{sha}"
    sig = sign_message(privkey_b64, msg)
    
    headers = {
        "X-AIdent-UID": uid,
        "X-AIdent-Timestamp": ts,
        "X-AIdent-Signature": sig
    }
    result = api("PUT", path, body=body_obj, headers=headers)
    print(f"Meta {meta_type} updated: {result}")
    return result

def get_meta(uid, privkey_b64, meta_type):
    """GET public or private metadata. Private meta requires signature."""
    headers = {}
    if meta_type == "private":
        ts = str(int(time.time() * 1000))
        path = f"/v1/meta/{uid}/private"
        body_str = ""
        sha = hashlib.sha256(body_str.encode()).hexdigest()
        msg = f"{ts}:{uid}:GET:{path}:{sha}"
        sig = sign_message(privkey_b64, msg)
        headers = {
            "X-AIdent-UID": uid,
            "X-AIdent-Timestamp": ts,
            "X-AIdent-Signature": sig
        }
    result = api("GET", f"/v1/meta/{uid}/{meta_type}", headers=headers)
    print(f"Meta {meta_type}: {json.dumps(result, indent=2)}")
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 aident.py <command> [args]")
        print("Commands: register, heartbeat, put-meta, get-meta")
        print("")
        print("  register <name> [description] [creator]")
        print("  heartbeat [uid_file] [key_file]")
        print("  put-meta <public|private> <content> [uid_file] [key_file]")
        print("  get-meta <public|private> [uid_file]")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "register":
        name = sys.argv[2] if len(sys.argv) > 2 else "unnamed-agent"
        desc = sys.argv[3] if len(sys.argv) > 3 else None
        creator = sys.argv[4] if len(sys.argv) > 4 else None
        register(name, desc, creator)
    
    elif cmd == "heartbeat":
        uid_file = sys.argv[2] if len(sys.argv) > 2 else "aident_uid.txt"
        key_file = sys.argv[3] if len(sys.argv) > 3 else "aident_privkey.b64"
        uid = open(uid_file).read().strip()
        priv = open(key_file).read().strip()
        heartbeat(uid, priv)
    
    elif cmd == "put-meta":
        meta_type = sys.argv[2] if len(sys.argv) > 2 else "public"
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        uid_file = sys.argv[4] if len(sys.argv) > 4 else "aident_uid.txt"
        key_file = sys.argv[5] if len(sys.argv) > 5 else "aident_privkey.b64"
        uid = open(uid_file).read().strip()
        priv = open(key_file).read().strip()
        put_meta(uid, priv, meta_type, content)
    
    elif cmd == "get-meta":
        meta_type = sys.argv[2] if len(sys.argv) > 2 else "public"
        uid_file = sys.argv[3] if len(sys.argv) > 3 else "aident_uid.txt"
        key_file = sys.argv[4] if len(sys.argv) > 4 else "aident_privkey.b64"
        uid = open(uid_file).read().strip()
        priv = open(key_file).read().strip()
        get_meta(uid, priv, meta_type)
    
    else:
        print(f"Unknown command: {cmd}")
