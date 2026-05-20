
# Minimal HTTP server serving files from a CL6 container with Range support.
# Usage:
#   python3 cl6_http_range_adapter.py --container release.cl6b --path data/big.bin --port 8080 [--toc release.cl6b.toc.json]
from http.server import HTTPServer, BaseHTTPRequestHandler
import argparse, re, json
from pathlib import Path
from cl6b.partial import extract_file, extract_file_fast

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self._handle(range_only=True)
    def do_GET(self):
        self._handle(range_only=False)

    def _handle(self, range_only=False):
        try:
            start, end = 0, None
            if 'Range' in self.headers:
                m = re.match(r'bytes=(\d+)-(\d+)?', self.headers['Range'])
                if m:
                    start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else None
            total = self.server.total_size
            s = start; e = end+1 if end is not None else total
            rng = f"{s}:{e}"
            if range_only:
                self.send_response(200)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(e - s))
                self.end_headers()
                return
            # Extract on the fly to a temp file (could be streamed; kept simple)
            outp = self.server.tmp_dir / "range.bin"
            if self.server.toc:
                extract_file_fast(self.server.container, str(self.server.toc), self.server.path, str(outp), rng)
            else:
                extract_file(self.server.container, self.server.path, str(outp), rng)
            data = outp.read_bytes()
            code = 206 if 'Range' in self.headers else 200
            self.send_response(code)
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Type', 'application/octet-stream')
            if 'Range' in self.headers:
                self.send_header('Content-Range', f'bytes {s}-{e-1}/{total}')
            self.end_headers()
            self.wfile.write(data)
        except Exception as ex:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(ex).encode())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--toc", default=None)
    ap.add_argument("--tmp-dir", default=".cl6_tmp")
    args = ap.parse_args()
    tmp = Path(args.tmp_dir); tmp.mkdir(exist_ok=True)
    # naive: compute total via full extract once (or via TOC if provided)
    total = None
    if args.toc:
        T = json.loads(Path(args.toc).read_text())
        total = T["files"][args.path]["total"]
    else:
        # Extract entire to get size (could be optimized)
        full = tmp / "full.bin"
        extract_file(args.container, args.path, str(full), None)
        total = full.stat().st_size
        full.unlink()
    httpd = HTTPServer(("0.0.0.0", args.port), Handler)
    httpd.container = args.container
    httpd.path = args.path
    httpd.total_size = total
    httpd.toc = Path(args.toc) if args.toc else None
    httpd.tmp_dir = tmp
    print(f"Serving {args.path} from {args.container} on http://127.0.0.1:{args.port}")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
