import re
import os

files_to_check = [
    '../templates/index.html',
    '../templates/results.html',
    '../templates/report.html',
    '../templates/search.html',
    '../templates/video_search.html',
    '../templates/dna_search.html'
]

replacements = [
    # Fix form-card and result-card backgrounds
    (r'background:\s*hsla\(220,\s*25%,\s*[0-9]+%,\s*[0-9.]+\);', r'background: var(--card-bg);'),
    # Fix white gradients for text (H1 tags) to use text color instead of white
    (r'#fff 30%', r'var(--text) 30%'),
    (r'#fff 0%', r'var(--text) 0%'),
    # Fix hardcoded white text
    (r'color:\s*#fff;', r'color: var(--text);'),
    (r'color:\s*rgba\(255,\s*255,\s*255,\s*([0-9.]+)\);', r'color: rgba(var(--text-rgb), \1);'),
    # Fix hardcoded dark inputs background
    (r'background:\s*rgba\(255,\s*255,\s*255,\s*0\.0[23]\);', r'background: var(--input-bg);'),
    # Fix hardcoded black backgrounds for images
    (r'background:\s*#000;', r'background: var(--surface-solid);'),
    (r'background:\s*#0a0a0a;', r'background: var(--surface-solid);'),
    # Fix hardcoded black text on primary buttons (should adapt or stay black?)
    # Primary buttons have gold background. Black text on gold is good in both modes.
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

print("HTML inline styles fixed.")
