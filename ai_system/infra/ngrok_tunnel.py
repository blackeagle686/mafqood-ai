import os
import sys
import time
from pyngrok import ngrok


def main():

    # ----------------------------------------------------------------
    # Read ngrok auth token
    # ----------------------------------------------------------------
    token = os.getenv(
        "NGROK_AUTHTOKEN",
        "3E2jOmRZkQ1RcYDCf2NpGuY18fd_49f6p422kjcp9bNPDWHZf"
    )

    # ----------------------------------------------------------------
    # IMPORTANT:
    # Priority order:
    # 1. NGROK_PORT  <- exported from deploy.sh
    # 2. DJANGO_PORT
    # 3. fallback 8001
    # ----------------------------------------------------------------
    port = int(
        os.getenv(
            "NGROK_PORT",
            os.getenv("DJANGO_PORT", "8001")
        )
    )

    print("====================================================")
    print("[*] Launching ngrok tunnel via pyngrok SDK...")
    print(f"[*] Target local port: {port}")
    print("====================================================")

    try:

        # ------------------------------------------------------------
        # Configure ngrok auth token
        # ------------------------------------------------------------
        ngrok.set_auth_token(token)

        # ------------------------------------------------------------
        # Kill previous tunnels ONLY from this process context
        # ------------------------------------------------------------
        try:
            ngrok.kill()
            time.sleep(1)
        except Exception:
            pass

        # ------------------------------------------------------------
        # Create HTTP tunnel
        # ------------------------------------------------------------
        tunnel = ngrok.connect(
            addr=port,
            proto="http"
        )

        # ------------------------------------------------------------
        # Public URL
        # ------------------------------------------------------------
        print(
            f"[+] Public ngrok URL: {tunnel.public_url}",
            flush=True
        )

        # ------------------------------------------------------------
        # Keep process alive
        # ------------------------------------------------------------
        while True:
            time.sleep(3600)

    except KeyboardInterrupt:

        print("\n[*] Shutting down ngrok tunnel gracefully...")
        ngrok.kill()

    except Exception as e:

        print(
            f"[!] ngrok error: {e}",
            file=sys.stderr,
            flush=True
        )

        sys.exit(1)


if __name__ == "__main__":
    main()