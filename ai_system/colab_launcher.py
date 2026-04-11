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
print(f"\n✨ Your application will be live at: {public_url}")

# 6. Launch Subsystems
print("\n👷 Starting Celery worker in background...")
os.chdir("app")
celery_process = subprocess.Popen(
    ["celery", "-A", "mafqood_project", "worker", "--loglevel=info"],
    stdout=subprocess.DEVNULL, # Keep logs clean, or redirect to a file
    stderr=subprocess.STDOUT
)

print("\n🔥 Launching Mafqood AI...")
# Start Django
try:
    print("⏳ Starting Django server...")
    run_command("python3 manage.py runserver --noreload 127.0.0.1:8000")
except KeyboardInterrupt:
    print("\n🛑 Stopping subsystems...")
finally:
    celery_process.terminate()
    ngrok.disconnect(public_url)
    print("👋 Shutdown complete.")
