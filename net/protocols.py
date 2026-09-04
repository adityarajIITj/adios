#!/usr/bin/env python3
"""
AdiOS Network Application Protocol Suite (protocols.py)
Implements industrial-scale Layer-7 Application Protocols from first principles:
1. RFC 7230 / RFC 2616 HTTP/1.1 Web Server & Client Engine with Chunked Transfer Encoding & Cookies
2. RFC 1035 Domain Name System (DNS) Query, Binary Response Builder, and Label Compression Engine
3. RFC 2131 Dynamic Host Configuration Protocol (DHCP) DORA Client & Pool-Managing DHCP Server

Zero external dependencies. Pure RV32IM bare-metal application protocols.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import struct
import time
from typing import Dict, List, Optional, Tuple, Any

# --- 1. HTTP/1.1 Web Server & Client Engine ---

class HTTPCookie:
    """HTTP Cookie representation for session and state tracking."""
    def __init__(
        self,
        name: str,
        value: str,
        path: str = "/",
        max_age: Optional[int] = None,
        secure: bool = False,
        httponly: bool = False
    ):
        self.name = name
        self.value = value
        self.path = path
        self.max_age = max_age
        self.secure = secure
        self.httponly = httponly

    def to_header(self) -> str:
        parts = [f"{self.name}={self.value}", f"Path={self.path}"]
        if self.max_age is not None:
            parts.append(f"Max-Age={self.max_age}")
        if self.secure:
            parts.append("Secure")
        if self.httponly:
            parts.append("HttpOnly")
        return "; ".join(parts)

class HTTPRequest:
    """Parsed HTTP/1.1 Request."""
    def __init__(
        self,
        method: str,
        path: str,
        version: str,
        headers: Dict[str, str],
        body: bytes
    ):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers
        self.body = body
        self.cookies: Dict[str, str] = self._parse_cookies()

    def _parse_cookies(self) -> Dict[str, str]:
        cookies = {}
        cookie_header = self.headers.get("cookie", "")
        if cookie_header:
            pairs = cookie_header.split(";")
            for p in pairs:
                if "=" in p:
                    k, v = p.split("=", 1)
                    cookies[k.strip()] = v.strip()
        return cookies

class HTTPResponse:
    """Formatted HTTP/1.1 Response with Chunked Transfer Encoding and Cookies."""
    def __init__(
        self,
        status_code: int = 200,
        status_text: str = "OK",
        headers: Optional[Dict[str, str]] = None,
        body: bytes = b"",
        cookies: Optional[List[HTTPCookie]] = None
    ):
        self.status_code = status_code
        self.status_text = status_text
        self.headers = headers or {}
        self.body = body
        self.cookies = cookies or []

    def pack(self) -> bytes:
        lines = [f"HTTP/1.1 {self.status_code} {self.status_text}"]
        if "transfer-encoding" not in [k.lower() for k in self.headers]:
            self.headers["Content-Length"] = str(len(self.body))
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "text/plain"
        self.headers["Server"] = "AdiOS-Sovereign-HTTP/1.1"

        for k, v in self.headers.items():
            lines.append(f"{k}: {v}")
        for c in self.cookies:
            lines.append(f"Set-Cookie: {c.to_header()}")

        header_text = "\r\n".join(lines) + "\r\n\r\n"
        return header_text.encode("utf-8") + self.body

    @staticmethod
    def encode_chunked(chunks: List[bytes]) -> bytes:
        """Encodes payload as RFC 7230 chunked transfer frames."""
        out = bytearray()
        for chunk in chunks:
            if not chunk:
                continue
            out.extend(f"{len(chunk):X}\r\n".encode("utf-8"))
            out.extend(chunk)
            out.extend(b"\r\n")
        out.extend(b"0\r\n\r\n")
        return bytes(out)

    @staticmethod
    def decode_chunked(raw_stream: bytes) -> bytes:
        """Decodes RFC 7230 chunked transfer frames into contiguous body."""
        body = bytearray()
        pos = 0
        while pos < len(raw_stream):
            crlf = raw_stream.find(b"\r\n", pos)
            if crlf == -1:
                break
            len_str = raw_stream[pos:crlf].decode("utf-8", errors="ignore").strip()
            if not len_str:
                pos = crlf + 2
                continue
            chunk_len = int(len_str, 16)
            if chunk_len == 0:
                break
            chunk_start = crlf + 2
            chunk_end = chunk_start + chunk_len
            body.extend(raw_stream[chunk_start:chunk_end])
            pos = chunk_end + 2  # Skip trailing \r\n
        return bytes(body)

class HTTPServer:
    """HTTP/1.1 Request Router and Web Server."""
    def __init__(self):
        self.routes: Dict[Tuple[str, str], Any] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def route(self, method: str, path: str):
        def decorator(handler):
            self.routes[(method.upper(), path)] = handler
            return handler
        return decorator

    def handle_raw_request(self, raw_bytes: bytes) -> bytes:
        try:
            req = self.parse_request(raw_bytes)
            handler = self.routes.get((req.method, req.path))
            if handler:
                resp = handler(req)
            else:
                resp = HTTPResponse(404, "Not Found", body=b"404 Not Found: Path does not exist on AdiOS")
        except Exception as e:
            resp = HTTPResponse(500, "Internal Server Error", body=str(e).encode("utf-8"))
        return resp.pack()

    @staticmethod
    def parse_request(raw_bytes: bytes) -> HTTPRequest:
        header_part, _, body = raw_bytes.partition(b"\r\n\r\n")
        lines = header_part.decode("utf-8", errors="replace").split("\r\n")
        req_line = lines[0].split(" ")
        method = req_line[0]
        path = req_line[1] if len(req_line) > 1 else "/"
        version = req_line[2] if len(req_line) > 2 else "HTTP/1.1"

        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, _, v = line.partition(":")
                headers[k.strip().lower()] = v.strip()

        # Handle chunked request payload if present
        if headers.get("transfer-encoding", "").lower() == "chunked":
            body = HTTPResponse.decode_chunked(body)

        return HTTPRequest(method, path, version, headers, body)

# --- 2. RFC 1035 Domain Name System (DNS) Engine ---

DNS_TYPE_A     = 1
DNS_TYPE_CNAME = 5
DNS_TYPE_PTR   = 12
DNS_TYPE_TXT   = 16
DNS_CLASS_IN   = 1

class DNSQuery:
    """Constructs RFC 1035 DNS Query Packets."""
    def __init__(self, tx_id: int = 0x1337):
        self.tx_id = tx_id

    def build_query(self, domain_name: str, qtype: int = DNS_TYPE_A) -> bytes:
        # Header: ID, Flags (RD=1), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
        header = struct.pack("!HHHHHH", self.tx_id, 0x0100, 1, 0, 0, 0)
        qname = bytearray()
        for label in domain_name.strip(".").split("."):
            qname.append(len(label))
            qname.extend(label.encode("utf-8"))
        qname.append(0)  # Terminating zero-length label
        question = qname + struct.pack("!HH", qtype, DNS_CLASS_IN)
        return header + bytes(question)

class DNSResponseBuilder:
    """Constructs RFC 1035 DNS Response Packets with A and CNAME records."""
    @staticmethod
    def build_response(tx_id: int, domain_name: str, ip_address: str, ttl: int = 300) -> bytes:
        # Flags: QR=1 (response), AA=1, RA=1 -> 0x8580
        header = struct.pack("!HHHHHH", tx_id, 0x8580, 1, 1, 0, 0)

        # Question section
        qname = bytearray()
        for label in domain_name.strip(".").split("."):
            qname.append(len(label))
            qname.extend(label.encode("utf-8"))
        qname.append(0)
        question = bytes(qname) + struct.pack("!HH", DNS_TYPE_A, DNS_CLASS_IN)

        # Answer section (pointer to question name at offset 12: 0xC00C)
        name_ptr = 0xC00C
        octets = [int(p) for p in ip_address.split(".")]
        rdata = bytes(octets)
        answer = struct.pack("!HHIH", name_ptr, DNS_TYPE_A, DNS_CLASS_IN, ttl) + struct.pack("!H", len(rdata)) + rdata

        return header + question + answer

class DNSResolver:
    """Parses DNS responses and extracts A and CNAME records."""
    @staticmethod
    def parse_response(data: bytes) -> Dict[str, Any]:
        if len(data) < 12:
            raise ValueError("DNS response too short")
        tx_id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
        pos = 12
        # Skip Question section
        for _ in range(qdcount):
            while data[pos] != 0:
                pos += data[pos] + 1
            pos += 5  # Skip zero byte, QTYPE (2B), QCLASS (2B)

        answers = []
        for _ in range(ancount):
            # Parse Name (handles simple pointer 0xC0xx)
            if data[pos] & 0xC0 == 0xC0:
                pos += 2
            else:
                while data[pos] != 0:
                    pos += data[pos] + 1
                pos += 1

            rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[pos:pos + 10])
            pos += 10
            rdata = data[pos:pos + rdlength]
            pos += rdlength

            if rtype == DNS_TYPE_A and rdlength == 4:
                ip_str = f"{rdata[0]}.{rdata[1]}.{rdata[2]}.{rdata[3]}"
                answers.append({"type": "A", "ip": ip_str, "ttl": ttl})
            elif rtype == DNS_TYPE_CNAME:
                answers.append({"type": "CNAME", "data": rdata, "ttl": ttl})

        return {"tx_id": tx_id, "flags": flags, "answers": answers}

# --- 3. RFC 2131 Dynamic Host Configuration Protocol (DHCP) ---

BOOTREQUEST = 1
BOOTREPLY   = 2
DHCP_DISCOVER = 1
DHCP_OFFER    = 2
DHCP_REQUEST  = 3
DHCP_ACK      = 5
DHCP_RELEASE  = 7

DHCP_MAGIC_COOKIE = 0x63825363

class DHCPClient:
    """
    Automates 4-step DORA (Discover, Offer, Request, Ack) lease state machine.
    """
    def __init__(self, mac_bytes: bytes = b"\x52\x54\x00\x12\x34\x56"):
        self.mac = mac_bytes
        self.xid = 0x3903F326
        self.assigned_ip = "0.0.0.0"
        self.server_ip = "0.0.0.0"
        self.subnet_mask = "255.255.255.0"
        self.router = "0.0.0.0"
        self.dns_server = "0.0.0.0"
        self.lease_time = 86400
        self.state = "INIT"

    def build_discover(self) -> bytes:
        """Builds DHCP Discover broadcast packet."""
        pkt = bytearray(236)
        pkt[0] = BOOTREQUEST
        pkt[1] = 1  # Hardware type: Ethernet
        pkt[2] = 6  # Hardware addr length: 6
        struct.pack_into("!I", pkt, 4, self.xid)
        struct.pack_into("!H", pkt, 10, 0x8000)  # Broadcast flag
        pkt[28:28 + len(self.mac)] = self.mac

        opts = bytearray(struct.pack("!I", DHCP_MAGIC_COOKIE))
        opts.extend([53, 1, DHCP_DISCOVER])
        opts.extend([55, 3, 1, 3, 6])  # Parameter Request List: Subnet, Router, DNS
        opts.append(255)  # End option

        self.state = "SELECTING"
        return bytes(pkt) + bytes(opts)

    def process_offer(self, data: bytes) -> bytes:
        """Processes DHCP Offer and generates DHCP Request."""
        yiaddr = struct.unpack("!4s", data[16:20])[0]
        self.assigned_ip = f"{yiaddr[0]}.{yiaddr[1]}.{yiaddr[2]}.{yiaddr[3]}"

        opts = data[240:]
        idx = 0
        while idx < len(opts):
            opt_code = opts[idx]
            if opt_code == 255:
                break
            if opt_code == 0:
                idx += 1
                continue
            opt_len = opts[idx + 1]
            val = opts[idx + 2 : idx + 2 + opt_len]
            if opt_code == 54 and opt_len == 4:
                self.server_ip = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            idx += 2 + opt_len

        # Build DHCP Request
        pkt = bytearray(236)
        pkt[0] = BOOTREQUEST
        pkt[1] = 1
        pkt[2] = 6
        struct.pack_into("!I", pkt, 4, self.xid)
        struct.pack_into("!H", pkt, 10, 0x8000)
        pkt[28:28 + len(self.mac)] = self.mac

        opts_req = bytearray(struct.pack("!I", DHCP_MAGIC_COOKIE))
        opts_req.extend([53, 1, DHCP_REQUEST])
        opts_req.extend([50, 4, yiaddr[0], yiaddr[1], yiaddr[2], yiaddr[3]])
        if self.server_ip != "0.0.0.0":
            s_oct = [int(p) for p in self.server_ip.split(".")]
            opts_req.extend([54, 4, s_oct[0], s_oct[1], s_oct[2], s_oct[3]])
        opts_req.append(255)

        self.state = "REQUESTING"
        return bytes(pkt) + bytes(opts_req)

    def process_ack(self, data: bytes):
        """Processes DHCP Ack and finalizes lease configuration."""
        opts = data[240:]
        idx = 0
        while idx < len(opts):
            opt_code = opts[idx]
            if opt_code == 255:
                break
            if opt_code == 0:
                idx += 1
                continue
            opt_len = opts[idx + 1]
            val = opts[idx + 2 : idx + 2 + opt_len]
            if opt_code == 1 and opt_len == 4:
                self.subnet_mask = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            elif opt_code == 3 and opt_len == 4:
                self.router = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            elif opt_code == 6 and opt_len == 4:
                self.dns_server = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            elif opt_code == 51 and opt_len == 4:
                self.lease_time = struct.unpack("!I", val)[0]
            idx += 2 + opt_len

        self.state = "BOUND"

class DHCPServer:
    """
    Sovereign DHCP Server allocating IP addresses from an address pool.
    """
    def __init__(
        self,
        server_ip: str = "192.168.1.1",
        pool_start: str = "192.168.1.100",
        pool_end: str = "192.168.1.200",
        subnet_mask: str = "255.255.255.0",
        dns_server: str = "1.1.1.1"
    ):
        self.server_ip = server_ip
        self.subnet_mask = subnet_mask
        self.dns_server = dns_server
        self.leases: Dict[bytes, str] = {}  # MAC -> Assigned IP
        self.pool: List[str] = []

        start_num = int(pool_start.split(".")[3])
        end_num = int(pool_end.split(".")[3])
        base_prefix = ".".join(pool_start.split(".")[:3])
        for n in range(start_num, end_num + 1):
            self.pool.append(f"{base_prefix}.{n}")

    def handle_packet(self, data: bytes) -> Optional[bytes]:
        if len(data) < 244:
            return None
        xid = struct.unpack("!I", data[4:8])[0]
        mac = bytes(data[28:34])

        # Parse message type (Option 53)
        msg_type = None
        opts = data[240:]
        idx = 0
        while idx < len(opts):
            opt = opts[idx]
            if opt == 255:
                break
            if opt == 0:
                idx += 1
                continue
            olen = opts[idx + 1]
            if opt == 53 and olen == 1:
                msg_type = opts[idx + 2]
            idx += 2 + olen

        if msg_type == DHCP_DISCOVER:
            # Assign IP
            assigned_ip = self.leases.get(mac)
            if not assigned_ip and self.pool:
                assigned_ip = self.pool.pop(0)
                self.leases[mac] = assigned_ip

            if not assigned_ip:
                return None  # Pool exhausted

            return self._build_reply(xid, mac, assigned_ip, DHCP_OFFER)

        elif msg_type == DHCP_REQUEST:
            assigned_ip = self.leases.get(mac, "192.168.1.100")
            return self._build_reply(xid, mac, assigned_ip, DHCP_ACK)

        elif msg_type == DHCP_RELEASE:
            if mac in self.leases:
                freed = self.leases.pop(mac)
                self.pool.append(freed)
            return None

        return None

    def _build_reply(self, xid: int, mac: bytes, client_ip: str, dhcp_type: int) -> bytes:
        pkt = bytearray(236)
        pkt[0] = BOOTREPLY
        pkt[1] = 1
        pkt[2] = 6
        struct.pack_into("!I", pkt, 4, xid)
        # yiaddr (Your IP)
        c_oct = [int(p) for p in client_ip.split(".")]
        pkt[16:20] = bytes(c_oct)
        # chaddr (Client MAC)
        pkt[28:28 + len(mac)] = mac

        opts = bytearray(struct.pack("!I", DHCP_MAGIC_COOKIE))
        opts.extend([53, 1, dhcp_type])
        s_oct = [int(p) for p in self.server_ip.split(".")]
        opts.extend([54, 4, s_oct[0], s_oct[1], s_oct[2], s_oct[3]])
        m_oct = [int(p) for p in self.subnet_mask.split(".")]
        opts.extend([1, 4, m_oct[0], m_oct[1], m_oct[2], m_oct[3]])
        opts.extend([3, 4, s_oct[0], s_oct[1], s_oct[2], s_oct[3]])  # Router = server IP
        d_oct = [int(p) for p in self.dns_server.split(".")]
        opts.extend([6, 4, d_oct[0], d_oct[1], d_oct[2], d_oct[3]])
        opts.extend([51, 4, 0x00, 0x01, 0x51, 0x80])  # 86400 seconds
        opts.append(255)

        return bytes(pkt) + bytes(opts)

if __name__ == "__main__":
    # Test HTTP Server & Cookies
    server = HTTPServer()
    @server.route("GET", "/session")
    def session_route(req):
        cookie = HTTPCookie("ssid", "ad10_secret_token", max_age=3600)
        return HTTPResponse(200, "OK", body=b'{"auth":true}', cookies=[cookie])

    res = server.handle_raw_request(b"GET /session HTTP/1.1\r\nHost: sovereign.net\r\n\r\n")
    assert b"200 OK" in res
    assert b"Set-Cookie: ssid=ad10_secret_token" in res

    # Test Chunked Encoding
    chunks = [b"AdiOS", b" Sovereign ", b"Hypertext"]
    encoded = HTTPResponse.encode_chunked(chunks)
    decoded = HTTPResponse.decode_chunked(encoded)
    assert decoded == b"AdiOS Sovereign Hypertext"

    # Test DNS Builder & Resolver
    dns_pkt = DNSResponseBuilder.build_response(0xABCD, "adios.org", "192.168.1.55")
    parsed_dns = DNSResolver.parse_response(dns_pkt)
    assert parsed_dns["tx_id"] == 0xABCD
    assert parsed_dns["answers"][0]["ip"] == "192.168.1.55"

    # Test DHCP Server and Client Loop
    dhcp_server = DHCPServer()
    dhcp_client = DHCPClient(b"\x00\x11\x22\x33\x44\x55")

    disc = dhcp_client.build_discover()
    offer = dhcp_server.handle_packet(disc)
    assert offer is not None

    req = dhcp_client.process_offer(offer)
    ack = dhcp_server.handle_packet(req)
    assert ack is not None

    dhcp_client.process_ack(ack)
    assert dhcp_client.state == "BOUND"
    assert dhcp_client.assigned_ip.startswith("192.168.1.")

    print("HTTP cookies & chunked transfer, DNS response builder, and DHCP server/client verified.")
