#!/usr/bin/env python3
"""Register an agent on AIdent.store and optionally set up heartbeat cron."""

import json, subprocess, sys, os, time, hashlib, tempfile
from pathlib import Path

API_BASE = "https://api.aident.store"

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
    return r.stdout.strip()

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
    """Generate Ed25519 keypair, return (private_b64, public_b64)."""
    priv = run("openssl genpkey -algorithm Ed25519 2>/dev/null | openssl base64 -A")
    pub = run(f"echo '{priv}' | openssl base64 -d -A | openssl pkey -pubout 2>/dev/null | openssl base64 -A")
    return priv, pub

def sign_message(privkey_b64, message):
    """Sign a message with Ed25519 private key using in-memory temp files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        priv_pem = os.path.join(tmpdir, "priv.pem")
        msg_file = os.path.join(tmpdir, "msg.txt")
        sig_file = os.path.join(tmpdir, "sig.bin")
        
        # Decode and write PEM with restrictive permissions
        run(f"echo '{privkey_b64}' | openssl base64 -d -A > {priv_pem}")
        os.chmod(priv_pem, 0o600)
        
        with open(msg_file, 'w') as f:
            f.write(message)
        
        run(f"openssl dgst -sha256 -sign {priv_pem} -out {sig_file} {msg_file}")
        sig = run(f"openssl base64 -A -in {sig_file}")
        return sig

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
    
    # Save private key with restrictive permissions
    key_path = Path.cwd() / "aident_privkey.b64"
    key_path.write_text(priv)
    key_path.chmod(0o600)
    print(f"  Private key saved to: {key_path} (permissions: 600)")
    
    uid_path = Path.cwd() / "aident_uid.txt"
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

def get_meta(uid, meta_type):
    """GET public or private metadata."""
    result = api("GET", f"/v1/meta/{uid}/{meta_type}")
    print(f"Meta {meta_type}: {json.dumps(result, indent=2)}")
    return result

def setup_cron(uid, privkey_b64, python_path="python3", interval_hours=12):
    """Set up a cron job for heartbeats. Script reads key from file, never embeds it."""
    script_path = f"{Path.cwd()}/aident_heartbeat.py"
    key_file = f"{Path.cwd()}/aident_privkey.b64"
    
    # Heartbeat script reads key from file at runtime (never embeds it)
    script = f'''#!/usr/bin/env {python_path}
"""AIdent heartbeat script. Reads private key from aident_privkey.b64 at runtime."""
import json, subprocess, sys, time, hashlib, tempfile, os

API_BASE = "https://api.aident.store"
UID = "{uid}"
KEY_FILE = "{key_file}"

def sign(message):
    with tempfile.TemporaryDirectory() as tmpdir:
        priv_pem = os.path.join(tmpdir, "priv.pem")
        msg_file = os.path.join(tmpdir, "msg.txt")
        sig_file = os.path.join(tmpdir, "sig.bin")
        with open(KEY_FILE, "r") as f:
            b64 = f.read().strip()
        subprocess.run(f"echo \'{{b64}}\' | openssl base64 -d -A > {{priv_pem}}", shell=True, capture_output=True)
        os.chmod(priv_pem, 0o600)
        with open(msg_file, "w") as f: f.write(message)
        subprocess.run(f"openssl dgst -sha256 -sign {{priv_pem}} -out {{sig_file}} {{msg_file}}", shell=True, capture_output=True)
        r = subprocess.run(f"openssl base64 -A -in {{sig_file}}", shell=True, capture_output=True, text=True)
        return r.stdout.strip()

def api(method, path, body=None, headers=None):
    cmd = ["curl","-s","-X",method,f"{{API_BASE}}{{path}}","-H","Content-Type: application/json"]
    if headers:
        for k,v in headers.items(): cmd += ["-H",f"{{k}}: {{v}}"]
    if body: cmd += ["-d",json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try: return json.loads(r.stdout)
    except: return {{"raw":r.stdout}}

ts = str(int(time.time()*1000))
p = "/v1/heartbeat"
b = ""
sha = hashlib.sha256(b.encode()).hexdigest()
sig = sign(f"{{ts}}:{{UID}}:POST:{{p}}:{{sha}}")
h = {{"X-AIdent-UID":UID,"X-AIdent-Timestamp":ts,"X-AIdent-Signature":sig}}
r = api("POST",p,headers=h)
print(r)
'''
    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, 0o755)
    
    cron_expr = f"0 */{interval_hours} * * *"
    cron_line = f"{cron_expr} {python_path} {script_path} >> /tmp/aident_heartbeat.log 2>&1"
    
    existing = subprocess.run("crontab -l 2>/dev/null", shell=True, capture_output=True, text=True).stdout
    if "aident_heartbeat" in existing:
        print("Cron job already exists. Skipping.")
    else:
        with open('/tmp/_cron', 'w') as f:
            f.write(existing + cron_line + "\n")
        subprocess.run("crontab /tmp/_cron", shell=True)
        os.remove('/tmp/_cron')
        print(f"Cron job set: every {interval_hours} hours")
    
    print(f"Heartbeat script: {script_path}")
    print(f"Key file: {key_file} (permissions: 600)")
    print(f"IMPORTANT: Keep {key_file} secure. Do not share or commit it.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 aident.py <command> [args]")
        print("Commands: register, heartbeat, put-meta, get-meta, setup-cron")
        print("")
        print("  register <name> [description] [creator]")
        print("  heartbeat [uid_file] [key_file]")
        print("  put-meta <public|private> <content> [uid_file] [key_file]")
        print("  get-meta <public|private> [uid_file]")
        print("  setup-cron [interval_hours]")
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
        uid = open(uid_file).read().strip()
        get_meta(uid, meta_type)
    
    elif cmd == "setup-cron":
        uid_file = sys.argv[2] if len(sys.argv) > 2 else "aident_uid.txt"
        key_file = sys.argv[3] if len(sys.argv) > 3 else "aident_privkey.b64"
        uid = open(uid_file).read().strip()
        priv = open(key_file).read().strip()
        interval = int(sys.argv[4]) if len(sys.argv) > 4 else 12
        setup_cron(uid, priv, interval_hours=interval)
    
    else:
        print(f"Unknown command: {cmd}")
