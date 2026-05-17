import sys
import time
from pyngrok import ngrok

def main():
    token = "3DqGR1alEbozJwsc2X1qhKUAJtC_4CEjQRnaypvLAz8jPoMgW"
    print("[*] Launching ngrok tunnel natively via pyngrok SDK...")
    try:
        # Set custom authentication token
        ngrok.set_auth_token(token)
        
        # Connect public HTTP tunnel to local port 8000
        tunnel = ngrok.connect(8000)
        
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
