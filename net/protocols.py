#!/usr/bin/env python3
"""
AdiOS Network Application Protocol Suite (protocols.py)
Implements Layer-7 Application Protocols:
1. RFC 7230 / RFC 2616 HTTP/1.1 Web Server & Client Engine
2. RFC 1035 Domain Name System (DNS) Query & Resolution Engine
3. RFC 2131 Dynamic Host Configuration Protocol (DHCP) DORA Client State Machine
Zero external dependencies.
"""

import struct
from typing import Dict, List, Optional, Tuple

# --- 1. HTTP/1.1 Web Server & Client Engine ---

class HTTPRequest:
    """Parsed HTTP/1.1 Request."""
    def __init__(self, method: str, path: str, version: str, headers: Dict[str, str], body: bytes):
        self.method = method
        self.path = path
        self.version = version
        self.headers = headers
        self.body = body

class HTTPResponse:
    """Formatted HTTP/1.1 Response."""
    def __init__(self, status_code: int = 200, status_text: str = "OK",
                 headers: Optional[Dict[str, str]] = None, body: bytes = b""):
        self.status_code = status_code
        self.status_text = status_text
        self.headers = headers or {}
        self.body = body

    def pack(self) -> bytes:
        lines = [f"HTTP/1.1 {self.status_code} {self.status_text}"]
        self.headers["Content-Length"] = str(len(self.body))
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "text/plain"
        self.headers["Server"] = "AdiOS-Sovereign-HTTP/1.1"

        for k, v in self.headers.items():
            lines.append(f"{k}: {v}")
        header_text = "\r\n".join(lines) + "\r\n\r\n"
        return header_text.encode("utf-8") + self.body

class HTTPServer:
    """HTTP/1.1 Request Router and Web Server."""
    def __init__(self):
        self.routes: Dict[Tuple[str, str], any] = {}

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

        return HTTPRequest(method, path, version, headers, body)

# --- 2. RFC 1035 Domain Name System (DNS) Engine ---

DNS_TYPE_A     = 1
DNS_TYPE_CNAME = 5
DNS_CLASS_IN   = 1

class DNSQuery:
    """Constructs RFC 1035 DNS Query Packets."""
    def __init__(self, tx_id: int = 0x1337):
        self.tx_id = tx_id

    def build_query(self, domain_name: str) -> bytes:
        # Header: ID, Flags (RD=1), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
        header = struct.pack("!HHHHHH", self.tx_id, 0x0100, 1, 0, 0, 0)
        qname = bytearray()
        for label in domain_name.strip(".").split("."):
            qname.append(len(label))
            qname.extend(label.encode("utf-8"))
        qname.append(0) # Terminating zero-length label
        question = qname + struct.pack("!HH", DNS_TYPE_A, DNS_CLASS_IN)
        return header + bytes(question)

class DNSResolver:
    """Parses DNS responses and extracts A records."""
    @staticmethod
    def parse_response(data: bytes) -> Dict[str, any]:
        tx_id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
        pos = 12
        # Skip Question section
        for _ in range(qdcount):
            while data[pos] != 0:
                pos += data[pos] + 1
            pos += 5 # Skip zero byte, QTYPE (2B), QCLASS (2B)

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

        return {"tx_id": tx_id, "flags": flags, "answers": answers}

# --- 3. RFC 2131 Dynamic Host Configuration Protocol (DHCP) Client ---

BOOTREQUEST = 1
BOOTREPLY   = 2
DHCP_DISCOVER = 1
DHCP_OFFER    = 2
DHCP_REQUEST  = 3
DHCP_ACK      = 5

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
        self.state = "INIT"

    def build_discover(self) -> bytes:
        """Builds DHCP Discover broadcast packet."""
        # 236-byte base BOOTP header
        pkt = bytearray(236)
        pkt[0] = BOOTREQUEST
        pkt[1] = 1 # Hardware type: Ethernet
        pkt[2] = 6 # Hardware addr length: 6
        struct.pack_into("!I", pkt, 4, self.xid)
        struct.pack_into("!H", pkt, 10, 0x8000) # Broadcast flag
        pkt[28:28 + len(self.mac)] = self.mac

        # Options with Magic Cookie
        opts = bytearray(struct.pack("!I", DHCP_MAGIC_COOKIE))
        opts.extend([53, 1, DHCP_DISCOVER]) # Option 53: DHCP Discover
        opts.extend([55, 3, 1, 3, 6])       # Parameter Request List: Subnet, Router, DNS
        opts.append(255) # End option

        self.state = "SELECTING"
        return bytes(pkt) + bytes(opts)

    def process_offer(self, data: bytes) -> bytes:
        """Processes DHCP Offer and generates DHCP Request."""
        yiaddr = struct.unpack("!4s", data[16:20])[0]
        self.assigned_ip = f"{yiaddr[0]}.{yiaddr[1]}.{yiaddr[2]}.{yiaddr[3]}"

        # Extract Server ID (Option 54)
        opts = data[240:]
        idx = 0
        while idx < len(opts):
            opt_code = opts[idx]
            if opt_code == 255: break
            if opt_code == 0: idx += 1; continue
            opt_len = opts[idx + 1]
            val = opts[idx + 2:idx + 2 + opt_len]
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
        opts_req.extend([50, 4, yiaddr[0], yiaddr[1], yiaddr[2], yiaddr[3]]) # Requested IP
        opts_req.append(255)

        self.state = "REQUESTING"
        return bytes(pkt) + bytes(opts_req)

    def process_ack(self, data: bytes):
        """Processes DHCP Ack and finalizes lease configuration."""
        opts = data[240:]
        idx = 0
        while idx < len(opts):
            opt_code = opts[idx]
            if opt_code == 255: break
            if opt_code == 0: idx += 1; continue
            opt_len = opts[idx + 1]
            val = opts[idx + 2:idx + 2 + opt_len]
            if opt_code == 1 and opt_len == 4:
                self.subnet_mask = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            elif opt_code == 3 and opt_len == 4:
                self.router = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            elif opt_code == 6 and opt_len == 4:
                self.dns_server = f"{val[0]}.{val[1]}.{val[2]}.{val[3]}"
            idx += 2 + opt_len

        self.state = "BOUND"

if __name__ == "__main__":
    # Test HTTP Server
    server = HTTPServer()
    @server.route("GET", "/status")
    def status_route(req):
        return HTTPResponse(200, "OK", body=b'{"status":"ONLINE","os":"AdiOS"}')

    res = server.handle_raw_request(b"GET /status HTTP/1.1\r\nHost: localhost\r\n\r\n")
    assert b"200 OK" in res
    assert b"ONLINE" in res

    # Test DNS Query
    dq = DNSQuery(0x4242).build_query("sovereign.adios")
    assert len(dq) > 20

    # Test DHCP Client
    dhcp = DHCPClient()
    disc = dhcp.build_discover()
    assert dhcp.state == "SELECTING"
    print("Layer-7 Network application protocols verified.")
