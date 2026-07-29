import json
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib import parse

from .multipart_parser import MultiPartParser
from .param_parser import ParamParser
from .req_wrapper import ReqWrapper
from .resp_builder import RespBuilder


class LocalServer(BaseHTTPRequestHandler):
    main_app = None

    def process(self, method, write=True):

        try:
            """Lambda functions seem to strip ending flashes so mimic that here"""
            self.path = self.path.rstrip("/")
            util = ParamParser()

            req = ReqWrapper()
            req.method = method
            req.body = {}
            req.query = {}
            req.form = {}
            req.file = {}

            parts = parse.urlparse(self.path)
            req.path = parts.path
            req.host = str(self.server.server_address)

            req.query = util.to_param_dict(parse.parse_qs(parts.query, keep_blank_values=True))

            req.headers = {}
            for k in self.headers.keys():
                req.headers[k] = self.headers.get(k)
                req.headers[k.lower()] = self.headers.get(k)

            content_length = self.headers.get('content-length')
            content_type = str(self.headers.get('content-type') or '').lower()
            if self.rfile and content_length:
                length = int(content_length)
                if content_type.startswith("multipart/form-data;"):
                    mpp = MultiPartParser(content_length=length)
                    mpp.parse(self.rfile, content_type=content_type, req=req)
                elif content_type.startswith("application/octet-stream"):
                    stream_data = self.rfile.read(length)
                    req.body = stream_data
                else:
                    field_data = self.rfile.read(length)
                    field_data = field_data.decode()
                    if 'json' in content_type or 'javascript' in content_type:
                        req.body = json.loads(field_data)
                    else:
                        req.body = util.to_param_dict(parse.parse_qs(field_data, keep_blank_values=True))

            resp: RespBuilder = LocalServer.main_app.handle(req)

            self.send_response(resp.status)
            for (key, val) in resp.headers.items():
                self.send_header(key, val)

            if resp.cache_output:
                # https://stackoverflow.com/questions/7071763/max-value-for-cache-control-header-in-http
                # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
                self.send_header("Cache-Control",
                                 "private, max-age=31536000, max-stale=3153600, stale-while-revalidate=3153600, stale-if-error=3153600, immutable")
            self.end_headers()

            if write:
                if resp.file_path:
                    CHUNK_SIZE = 262144
                    with open(resp.file_path, 'rb') as f:
                        file_data = f.read(CHUNK_SIZE)
                        while file_data:
                            self.wfile.write(file_data)
                            file_data = f.read(CHUNK_SIZE)
                else:
                    self.wfile.write(resp.body.encode())
        except Exception as ex:
            print(ex)
            try:
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "*")
                self.send_header("Content-Type", "text")
                self.end_headers()

                stack = traceback.format_exc()
                content = f"""Error processing request: {ex}
                    ----💥--🤮-🧯-🔥-🤯-🔥-😬-😭---💥--
                    {stack}""".replace("\n", "<br>")
                error_page = f"""<!DOCTYPE html><html lang="en">
                    <style>body{{color:red;}}</style>
                    <head><meta charset="UTF-8">
                    <title>Error</title></head>
                    <body>{content}</body></html>"""
                self.wfile.write(error_page.encode())
            except Exception as superex:
                print("error handling request exception")
                print(superex)
            raise ex

    def do_HEAD(self):
        self.process(method='HEAD', write=False)

    def do_GET(self):
        self.process(method='GET')

    def do_POST(self):
        self.process(method='POST')

    def do_DELETE(self):
        self.process(method='DELETE')

    def do_PUT(self):
        self.process(method='PUT')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()

    @classmethod
    def run(cls, application, port=8080):
        cls.main_app = application
        print(f"sys.argv {sys.argv}")
        server_address = ('', port)
        httpd = HTTPServer(server_address, LocalServer)
        print('Starting httpd on port {}...'.format(port))
        print(f'http://localhost:{port}/')
        # https://stackoverflow.com/questions/4419650/how-to-implement-timeout-in-basehttpserver-basehttprequesthandler-python
        httpd.timeout = 60

        def on_TIMEOUT():
            print("request timeout")

        httpd.handle_timeout = on_TIMEOUT
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("server manually exiting")
            httpd.shutdown()
            print("exited")
        except Exception as ex:
            print("unexpected exception")
            print(ex)
