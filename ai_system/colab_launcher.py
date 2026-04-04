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
os.environ["CELERY_ALWAYS_EAGER"] = "True"

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
authtoken = getpass("Enter your Ngrok Authtoken (from https://dashboard.ngrok.com/): ")
from pyngrok import ngrok
ngrok.set_auth_token(authtoken)

# 4. Database Migrations
print("\n🗄️ Running database migrations...")
os.environ["PYTHONPATH"] = f"{os.getcwd()}:{os.getcwd()}/app:" + os.environ.get("PYTHONPATH", "")
run_command("cd app && python3 manage.py migrate")

# 5. Open Tunnel
print("\n🌐 Creating Ngrok tunnel...")
# Using 127.0.0.1 explicitly to avoid IPv6 issues
public_url = ngrok.connect("127.0.0.1:8000", bind_tls=True).public_url
print(f"\n✨ Your application will be live at: {public_url}")
print("⚠️  IMPORTANT: Wait until you see 'Quit the server with CONTROL-C' before clicking the link!")

# 6. Launch Django
print("\n🔥 Launching Mafqood AI...")
# Add current paths to PYTHONPATH
os.chdir("app")

# Start Django
try:
    print("⏳ Starting Django server (this may take 10-20 seconds)...")
    # Using --noreload to avoid double-startup issues on Colab
    run_command("python3 manage.py runserver --noreload 127.0.0.1:8000")
except KeyboardInterrupt:
    print("\n🛑 Stopping server...")
finally:
    ngrok.disconnect(public_url)
