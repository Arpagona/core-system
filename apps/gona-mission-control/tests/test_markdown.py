import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MarkdownTests(unittest.TestCase):
    def setUp(self):
        self.node = shutil.which('node')
        if not self.node:
            self.skipTest('node indisponible')

    def render(self, text):
        script = ('const m=require(' + json.dumps(str(ROOT / 'web/markdown.js')) + ');'
                  'process.stdout.write(m.renderMarkdown(' + json.dumps(text) + '));')
        return subprocess.check_output([self.node, '-e', script], text=True, timeout=10)

    def test_escapes_html(self):
        out = self.render('<img src=x onerror=alert(1)>')
        self.assertNotIn('<img src=x', out)
        self.assertIn('&lt;img', out)

    def test_markdown_blocks_and_links(self):
        out = self.render('## Titre\n\n- **gras** et `code`\n- [lien](https://example.test/a?b=1)\n\n```\nx < y\n```')
        self.assertIn('<h2>Titre</h2>', out)
        self.assertIn('<ul><li><strong>gras</strong> et <code>code</code></li>', out)
        self.assertIn('href="https://example.test/a?b=1"', out)
        self.assertIn('<pre><code>x &lt; y</code></pre>', out)

    def test_rejects_javascript_links(self):
        out = self.render('[x](javascript:alert(1))')
        self.assertNotIn('href=', out)

    def test_media_path_is_encoded(self):
        out = self.render('MEDIA:/tmp/a&b.png')
        self.assertIn('/api/media?path=', out)
        self.assertIn('%2Ftmp%2Fa%26b.png', out)


if __name__ == '__main__':
    unittest.main()
