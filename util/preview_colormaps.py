#!/usr/bin/env python
import html
import http.server
import os

from colormap import Colormap

source_dir = "colormaps"


def generate_preview() -> str:
    out = ""
    for entry in sorted(os.scandir(source_dir), key=lambda e: e.name):
        if entry.is_file():
            fpath = os.path.join(source_dir, entry.name)
            cmap = Colormap.read(fpath)

            out += '<section>'
            out += '<h2>' + html.escape(entry.name) + '</h2>'
            out += '<p>' + html.escape(cmap.doc_comment) + '</p>'
            out += '<div>' + cmap.html_legend() + '</div>'
            out += '</section>'
    return out


response_tmpl = """<!DOCTYPE html>
<html>
<head>
    <title>Preview colormaps - weather-maps</title>
    <link rel="shortcut icon" type="image/x-icon" href="data:image/x-icon;,">
    
    <style>
        body {
            font-family: "system-ui";
            color: rgb(51, 65, 85);
        }
        
        .preview {
            font-size: 12px;
            width: 100%;
            max-width: 400px;
        }
        
        .preview .source {
            overflow: auto;
            max-height: 4em;
        }
        
        .legend-layer-content {
            opacity: 0.8;
        }
    </style>
</head>
<body>
<h1>Preview colormaps</h1>
<div class="preview">__PREVIEW__</div>
</body>
</html>"""


# noinspection PyPep8Naming
class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        preview = generate_preview()

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        self.wfile.write(response_tmpl.replace("__PREVIEW__", preview).encode('utf-8'))
        self.wfile.flush()


if __name__ == '__main__':
    addr = ('', 8080)
    print(f"Listening on {addr[0]}:{addr[1]}")
    httpd = http.server.HTTPServer(addr, RequestHandler)
    httpd.serve_forever()
