import os
import sys
import time
from pyngrok import ngrok

def main():
    token = os.getenv("NGROK_AUTHTOKEN", "3E2ijNAk9Jj7Wr2WDftflTw51qp_3PTrGmivVSWQjnubWTsWc")
    print("[*] Launching ngrok tunnel natively via pyngrok SDK...")
    try:
        # Set custom authentication token
        ngrok.set_auth_token(token)
        
        # Connect public HTTP tunnel to local port 8000
        tunnel = ngrok.connect(8000, options={"pooling_enabled": "true"})
        
        # Print the live public URL (deploy.sh will parse this)
        print(f"[+] Public ngrok URL: {tunnel.public_url}", flush=True)
        
        # Keep the script running to keep the tunnel open
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[*] Shutting down ngrok tunnel gracefully.")
        ngrok.kill()
    except Exception as e:
        print(f"[!] ngrok error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
