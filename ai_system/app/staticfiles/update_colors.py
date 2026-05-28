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

primary_replacements = [
    (r'rgba\(0,\s*242,\s*255,\s*([0-9.]+)\)', r'rgba(var(--primary-rgb), \1)'),
    (r'hsla\(182,\s*100%,\s*50%,\s*([0-9.]+)\)', r'rgba(var(--primary-rgb), \1)')
]

secondary_replacements = [
    (r'rgba\(131,\s*0,\s*255,\s*([0-9.]+)\)', r'rgba(var(--secondary-rgb), \1)'),
    (r'hsla\(266,\s*100%,\s*50%,\s*([0-9.]+)\)', r'rgba(var(--secondary-rgb), \1)')
]

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r') as f:
        content = f.read()
    
    for pattern, replacement in primary_replacements + secondary_replacements:
        content = re.sub(pattern, replacement, content)
        
    with open(filepath, 'w') as f:
        f.write(content)

print("Colors updated.")
