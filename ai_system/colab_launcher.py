# colab_launcher.py
import os
import sys
import subprocess
from getpass import getpass

def run_command(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='')
    process.wait()

print("🚀 Starting Colab Deployment...")

# 0. Set Environment Variables
# Removed CELERY_ALWAYS_EAGER=True to allow real background processing

# 1. Install System Dependencies
print("\n📦 Installing Redis...")
run_command("sudo apt-get install -y redis-server")
run_command("sudo service redis-server start")

# 2. Install Python Dependencies
print("\n🐍 Installing Python packages...")
run_command("pip install pyngrok")
run_command("pip install -r app/requirements.txt")

# 3. Setup Ngrok
print("\n🌐 Setting up Ngrok...")
authtoken = getpass("Enter your Ngrok Authtoken: ")
from pyngrok import ngrok
ngrok.set_auth_token(authtoken)

# 4. Database Migrations
print("\n🗄️ Running database migrations...")
os.environ["PYTHONPATH"] = f"{os.getcwd()}:{os.getcwd()}/app:" + os.environ.get("PYTHONPATH", "")
run_command("cd app && python3 manage.py migrate")

# 5. Open Tunnel
print("\n🌐 Creating Ngrok tunnel...")
public_url = ngrok.connect("127.0.0.1:8000", bind_tls=True).public_url

# 6. Launch Subsystems
print("\n👷 Starting Celery worker in background...")
os.chdir("app")
celery_process = subprocess.Popen(
    ["celery", "-A", "mafqood_project", "worker", "--loglevel=info"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT
)

def wait_for_port(port, timeout=60):
    import socket
    import time
    start_time = time.time()
    while True:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(2)
            if time.time() - start_time > timeout:
                return False

print("\n🔥 Launching Mafqood AI...")
# Start Django
try:
    # Run server in background so we can wait for it
    django_process = subprocess.Popen(
        ["python3", "manage.py", "runserver", "--noreload", "127.0.0.1:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    print("⏳ Waiting for Django to boot (this usually takes 15-30s)...")
    if wait_for_port(8000):
        print(f"\n✨ SUCCESS! Your application is live at: {public_url}")
        print("🚀 You can now start sending requests to the API.")
    else:
        print("\n❌ Error: Django took too long to start.")
    
    # Stream Django logs to console
    for line in django_process.stdout:
        print(line, end='')

except KeyboardInterrupt:
    print("\n🛑 Stopping subsystems...")
finally:
    try: django_process.terminate()
    except: pass
    celery_process.terminate()
    ngrok.disconnect(public_url)
    print("👋 Shutdown complete.")
