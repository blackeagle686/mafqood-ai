import os
import re

files_to_check = [
    '../templates/index.html',
    '../templates/results.html',
    '../templates/report.html',
    '../templates/search.html',
    '../templates/video_search.html',
    '../templates/dna_search.html'
]

toggle_html = """                <button id="theme-toggle" title="تغيير المظهر" style="background:none; border:none; color: var(--text); cursor:pointer; font-size:1.2rem; margin-right: 1.5rem; transition: color 0.3s;">
                    <i class="fa-solid fa-moon"></i>
                </button>
            </div>"""

script_js = """    <script>
        // Theme Toggle Logic
        const themeToggle = document.getElementById('theme-toggle');
        const themeIcon = themeToggle ? themeToggle.querySelector('i') : null;
        
        // Check for saved theme
        const currentTheme = localStorage.getItem('theme') || 'dark';
        if (currentTheme === 'light') {
            document.documentElement.setAttribute('data-theme', 'light');
            if (themeIcon) {
                themeIcon.classList.remove('fa-moon');
                themeIcon.classList.add('fa-sun');
            }
        }
        
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                let theme = document.documentElement.getAttribute('data-theme');
                if (theme === 'light') {
                    document.documentElement.removeAttribute('data-theme');
                    localStorage.setItem('theme', 'dark');
                    themeIcon.classList.remove('fa-sun');
                    themeIcon.classList.add('fa-moon');
                } else {
                    document.documentElement.setAttribute('data-theme', 'light');
                    localStorage.setItem('theme', 'light');
                    themeIcon.classList.remove('fa-moon');
                    themeIcon.classList.add('fa-sun');
                }
            });
        }
    </script>
</body>"""

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add toggle to nav-links
    if '<button id="theme-toggle"' not in content:
        content = re.sub(r'\s*</div>\s*</div>\s*</nav>', '\n' + toggle_html + '\n        </div>\n    </nav>', content)
        
    # Add script before </body>
    if '// Theme Toggle Logic' not in content:
        content = content.replace('</body>', script_js)
        
    with open(filepath, 'w') as f:
        f.write(content)

print("Theme toggle added.")
