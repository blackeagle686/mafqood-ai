import os

files_to_check = [
    '../templates/results.html',
    '../templates/report.html',
    '../templates/search.html',
    '../templates/video_search.html',
    '../templates/dna_search.html'
]

footer_html = """
    <!-- ===================== FOOTER ===================== -->
    <footer class="site-footer" style="padding: 2rem 0; border-top: 1px solid var(--border-color); background: var(--surface); margin-top: 4rem;">
        <div class="container" style="text-align: center;">
            <div class="footer-logo" style="color: var(--primary); font-size: 1.2rem; font-weight: 800;">
                <i class="fa-solid fa-hands-holding-child"></i> مفقود
            </div>
            <p style="color: var(--text-muted); font-size: 0.9rem; margin-top: 0.5rem;">
                منصة إنسانية مدعومة بالذكاء الاصطناعي — جميع الحقوق محفوظة © 2026
            </p>
        </div>
    </footer>
"""

for filepath in files_to_check:
    if not os.path.exists(filepath):
        continue
    with open(filepath, 'r') as f:
        content = f.read()
    
    if '<footer class="site-footer"' not in content:
        # We need to insert it right before the scripts or </body>
        if '<script>' in content:
            # find first <script> that is near the end, or just split on the last <script> block
            parts = content.rsplit('<script>', 1)
            if len(parts) == 2:
                content = parts[0] + footer_html + '\n    <script>' + parts[1]
            else:
                content = content.replace('</body>', footer_html + '\n</body>')
        else:
            content = content.replace('</body>', footer_html + '\n</body>')
        
        with open(filepath, 'w') as f:
            f.write(content)

print("Footer added to all templates.")
