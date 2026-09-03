#!/usr/bin/env python3
"""
AdiOS Networking Subsystem: Sovereign Cyber Telnet Server (telnet.py)
Implements RFC 854 Telnet Protocol and connects remote network sessions
directly into the Sovereign Cyber Shell.
Features:
- RFC 854 IAC (Interpret As Command) command negotiation handling
- Line-buffered terminal input with ANSI terminal styling
- Integrated Sovereign Cyber Shell command execution over network packets
"""

import sys
import os

from holy.holy_shell import SovereignCyberShell

TELNET_IAC   = 255
TELNET_DONT  = 254
TELNET_DO    = 253
TELNET_WONT  = 252
TELNET_WILL  = 251
TELNET_SE    = 240
TELNET_NOP   = 241
TELNET_SB    = 250

TELNET_OPT_ECHO = 1
TELNET_OPT_SGA  = 3

class TelnetSession:
    """
    Stateful RFC 854 Telnet terminal session.
    """
    def __init__(self, remote_ip, remote_port, shell=None):
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.shell = shell or SovereignCyberShell()
        self.input_buffer = bytearray()
        self.iac_state = 0 # 0: NORMAL, 1: IAC, 2: WILL/WONT/DO/DONT

    def process_incoming_bytes(self, data: bytes) -> tuple:
        """
        Parses incoming Telnet byte stream, filtering out negotiations.
        Returns (executed_responses_list, iac_replies_bytes).
        """
        replies = bytearray()
        executed_outputs = []

        for b in data:
            if self.iac_state == 0:
                if b == TELNET_IAC:
                    self.iac_state = 1
                elif b in (ord("\r"), ord("\n")):
                    if len(self.input_buffer) > 0:
                        cmd_line = self.input_buffer.decode("utf-8", errors="replace").strip()
                        self.input_buffer.clear()
                        if cmd_line:
                            output = self.shell.execute_line(cmd_line)
                            executed_outputs.append((cmd_line, output))
                elif b in (8, 127): # Backspace
                    if len(self.input_buffer) > 0:
                        self.input_buffer.pop()
                else:
                    self.input_buffer.append(b)
            elif self.iac_state == 1:
                # Got IAC, expecting command
                if b in (TELNET_DO, TELNET_DONT, TELNET_WILL, TELNET_WONT):
                    self.iac_command = b
                    self.iac_state = 2
                else:
                    self.iac_state = 0
            elif self.iac_state == 2:
                # Option code
                opt = b
                if self.iac_command == TELNET_DO:
                    # Reply WONT to all requests except SGA
                    if opt == TELNET_OPT_SGA:
                        replies.extend([TELNET_IAC, TELNET_WILL, opt])
                    else:
                        replies.extend([TELNET_IAC, TELNET_WONT, opt])
                elif self.iac_command == TELNET_WILL:
                    # Reply DO to SGA, DONT to others
                    if opt == TELNET_OPT_SGA:
                        replies.extend([TELNET_IAC, TELNET_DO, opt])
                    else:
                        replies.extend([TELNET_IAC, TELNET_DONT, opt])
                self.iac_state = 0

        return executed_outputs, bytes(replies)

class CyberTelnetServer:
    """
    Sovereign Telnet Server binding to UDP port 2323 on the NetworkStack.
    """
    def __init__(self, stack, port=2323):
        self.stack = stack
        self.port = port
        self.sock = None
        self.sessions = {} # (ip, port) -> TelnetSession
        if self.stack:
            from net.transport import UDPSocket
            self.sock = UDPSocket(self.stack, self.port)

    def poll(self):
        """Polls incoming UDP datagrams and executes Telnet sessions."""
        if not self.sock:
            return []

        events = []
        while True:
            data, addr = self.sock.recvfrom()
            if not data:
                break
            client_ip, client_port = addr
            session_key = (client_ip, client_port)
            if session_key not in self.sessions:
                self.sessions[session_key] = TelnetSession(client_ip, client_port)
                # Send welcome banner
                banner = (
                    "\r\n===========================================================\r\n"
                    "        AdiOS SOVEREIGN CYBER TELNET TERMINAL             \r\n"
                    "===========================================================\r\n"
                    "Connected to bare-metal RISC-V sovereign computing node.\r\n"
                    "Type 'help' for command index.\r\n\r\n"
                    "adios-remote> "
                ).encode("utf-8")
                self.sock.sendto(banner, client_ip, client_port)

            session = self.sessions[session_key]
            executed, iac_replies = session.process_incoming_bytes(data)

            if iac_replies:
                self.sock.sendto(iac_replies, client_ip, client_port)

            for cmd, out in executed:
                events.append((client_ip, cmd, out))
                resp = f"\r\n{out}\r\nadios-remote> ".encode("utf-8")
                self.sock.sendto(resp, client_ip, client_port)

        return events

if __name__ == "__main__":
    session = TelnetSession("127.0.0.1", 5000)
    executed, replies = session.process_incoming_bytes(b"oracle 8\r\n")
    print(f"Executed: {len(executed)} command(s)")
    for cmd, out in executed:
        print(f"Command: '{cmd}' -> Output:\n{out}")
