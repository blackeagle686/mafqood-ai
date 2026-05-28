import re
import os

filepath = '../templates/index.html'

if os.path.exists(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace hsla(313, 100%, 50%, 0.xx)
    content = re.sub(r'hsla\(313,\s*100%,\s*50%,\s*([0-9.]+)\)', r'rgba(var(--accent-rgb), \1)', content)
    # Also rgba(255, 0, 255, 0.xx) just in case
    
    with open(filepath, 'w') as f:
        f.write(content)

print("Accent updated.")
