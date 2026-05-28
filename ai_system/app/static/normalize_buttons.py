import re
import os

files_to_check = [
    'style.css',
    '../templates/index.html',
    '../templates/results.html',
    '../templates/report.html',
    '../templates/search.html',
    '../templates/video_search.html',
    '../templates/dna_search.html'
]

replacements = [
    (r'linear-gradient\(135deg,\s*var\(--primary\),\s*hsl\(200,\s*100%,\s*45%\)\)', r'linear-gradient(135deg, var(--primary), var(--secondary))'),
    (r'linear-gradient\(135deg,\s*var\(--accent\),\s*hsl\(266,\s*100%,\s*50%\)\)', r'linear-gradient(135deg, var(--accent), var(--secondary))')
]

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r') as f:
        content = f.read()
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
        
    with open(filepath, 'w') as f:
        f.write(content)

print("Buttons normalized.")
