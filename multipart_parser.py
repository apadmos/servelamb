from req_wrapper import ReqWrapper


class MultiPartParser(object):

    def __init__(self, content_length:int):
        self.read_count = 0
        self.stream = None
        self.leftover_bytes = bytearray()
        self.content_length = content_length
        """10 MB?"""
        self.chunk_size = 10240

    def read_until(self, marker):
        read_bytes = self.leftover_bytes or bytearray()
        while self.read_count < self.content_length and marker not in read_bytes:
            read_size = min(self.chunk_size, self.content_length - self.read_count)
            read_chunk = self.stream.read(read_size)
            read_bytes += read_chunk
            "update status based on what was actually read, not what you hoped for"
            self.read_count += len(read_chunk)
        """we've either now found what we want, or run out of content"""
        if marker in read_bytes:
            marker_pos = read_bytes.index(marker)
            return_val = read_bytes[:marker_pos]
            self.leftover_bytes = read_bytes[marker_pos + len(marker):]
            return return_val
        return None



    def parse_local_headers(self, header_string:str):
        local_headers = {
            "Content-Type": "text/plain"
        }
        for header in header_string.split("\r\n"):
            parts = header.split(":")
            if len(parts) == 2:
                local_headers[parts[0].strip()] = parts[1].strip()
        return local_headers

    def parse_content_disposition(self, content_disposition:str):
        """
        \r\nContent-Disposition: form-data; name="file"; filename="524d97e7acaa0e35cfcfd546f54c9ace7e234893-1.jpeg"
        :param content_disposition:
        :return:
        """
        local_headers = {
        }
        for part in content_disposition.split(";"):
            sub_parts = part.split('="')
            if len(sub_parts) == 2:
                local_headers[sub_parts[0].strip(' "')] = sub_parts[1].strip(' "')
        return local_headers

    def parse(self, stream, content_type, req:ReqWrapper):
        """https://www.w3.org/TR/html401/interact/forms.html#h-17.13.4

b'------WebKitFormBoundary1I6NgnMHUIQxpdF2\r\n
Content-Disposition: form-data; name="uploaded_file"; filename="524d97e7acaa0e35cfcfd546f54c9ace7e234893-1.jpeg"
\r\nContent-Type: image/jpeg
\r\n
\r\n\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x000\x00\x0f\xff\xd9
\r\n------WebKitFormBoundary1I6NgnMHUIQxpdF2
\r\nContent-Disposition: form-data; name="other_data"
\r\n
\r\nsome value
\r\n------WebKitFormBoundary1I6NgnMHUIQxpdF2--
\r\n'
        """
        boundary = content_type[content_type.index("boundary=") + 9:]
        boundary_start = f"--{boundary}".encode()
        boundary_middle = f"\r\n--{boundary}".encode()
        boundary_end = f"--{boundary}--".encode()
        self.stream = stream
        spacer = "\r\n\r\n".encode()

        self.read_until(boundary_start)
        while self.read_count < self.content_length or self.leftover_bytes:
            headers = self.read_until(spacer)
            if not headers:
                break
            headers = self.parse_local_headers(headers.decode())
            contest_disposition = self.parse_content_disposition(headers["Content-Disposition"])

            if 'text' in headers["Content-Type"]:
                value = self.read_until(boundary_middle)
                value = value.decode().strip()
                req.body[contest_disposition["name"]] = value
            else:
                if req.file:
                    raise Exception("Multiple files found in request, we don't handle that")
                req.file = headers
                req.file["filename"] = contest_disposition["filename"]
                req.file["field_name"] = contest_disposition["name"]

                """this is where you could try streaming if you wanted"""
                req.file[contest_disposition["name"]] = self.read_until(boundary_middle)
            print(self.read_count)
        return req






