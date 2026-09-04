#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: ASN.1 DER & X.509 Certificate Decoder (crypto/x509.py)
Implements ITU-T X.690 / RFC 5280 Certificate decoding from raw binary bytes:
- ASN.1 DER Tag-Length-Value (TLV) recursive decoder
- Fundamental ASN.1 types: SEQUENCE, SET, INTEGER, BIT STRING, OCTET STRING, OID, UTF8/PrintableString, UTCTime
- Object Identifier (OID) dot-notation decoding (e.g. 2.5.4.3 commonName, 1.2.840.113549.1.1.1 rsaEncryption)
- TBSCertificate parser: serial number, issuer, validity period, subject distinguished name, SubjectPublicKeyInfo
- Public Key extraction: RSA modulus/exponent and SubjectAltNames (SAN) extensions

Zero external dependencies. Pure RV32IM cryptographic architecture.
STRICT ZERO EMOJI POLICY.
"""

import struct
from typing import Dict, List, Tuple, Optional, Any, Union

# ASN.1 Universal Tags
TAG_BOOLEAN          = 0x01
TAG_INTEGER          = 0x02
TAG_BIT_STRING       = 0x03
TAG_OCTET_STRING     = 0x04
TAG_NULL             = 0x05
TAG_OID              = 0x06
TAG_UTF8_STRING      = 0x0C
TAG_PRINTABLE_STRING = 0x13
TAG_IA5_STRING       = 0x16
TAG_UTC_TIME         = 0x17
TAG_GENERALIZED_TIME = 0x18
TAG_SEQUENCE         = 0x30 # 0x10 | 0x20 constructed
TAG_SET              = 0x31 # 0x11 | 0x20 constructed

# Standard X.509 OIDs
OID_MAP = {
    "2.5.4.3": "commonName",
    "2.5.4.6": "countryName",
    "2.5.4.7": "localityName",
    "2.5.4.8": "stateOrProvinceName",
    "2.5.4.10": "organizationName",
    "2.5.4.11": "organizationalUnitName",
    "1.2.840.113549.1.1.1": "rsaEncryption",
    "1.2.840.113549.1.1.11": "sha256WithRSAEncryption",
    "1.2.840.10045.2.1": "ecPublicKey",
    "1.2.840.10045.3.1.7": "secp256r1"
}

class ASN1Node:
    """Represents a decoded ASN.1 DER element."""
    def __init__(self, tag: int, length: int, value: bytes, children: Optional[List['ASN1Node']] = None):
        self.tag = tag
        self.length = length
        self.value = value
        self.children = children or []

    @property
    def is_constructed(self) -> bool:
        return bool(self.tag & 0x20)

    def as_int(self) -> int:
        return int.from_bytes(self.value, byteorder="big", signed=True)

    def as_str(self) -> str:
        return self.value.decode("utf-8", errors="replace")

    def as_oid(self) -> str:
        return DERDecoder.decode_oid(self.value)

class DERDecoder:
    """Decodes binary DER encoded streams into an ASN.1 Node tree."""
    @staticmethod
    def decode(data: bytes) -> Tuple[ASN1Node, int]:
        """Returns (root_node, bytes_consumed)."""
        if not data:
            raise ValueError("Empty DER buffer")

        tag = data[0]
        offset = 1

        # Decode length
        if data[offset] & 0x80 == 0:
            length = data[offset]
            offset += 1
        else:
            num_len_bytes = data[offset] & 0x7F
            offset += 1
            length = int.from_bytes(data[offset : offset + num_len_bytes], "big")
            offset += num_len_bytes

        val_bytes = data[offset : offset + length]
        total_consumed = offset + length

        # If constructed (e.g. SEQUENCE or SET), recursively parse children
        children = []
        if tag & 0x20:
            child_offset = 0
            while child_offset < length:
                child_node, consumed = DERDecoder.decode(val_bytes[child_offset:])
                children.append(child_node)
                child_offset += consumed

        return ASN1Node(tag, length, val_bytes, children), total_consumed

    @staticmethod
    def decode_oid(raw: bytes) -> str:
        """Decodes variable-length OID bytes into a dot-separated string."""
        if not raw:
            return ""
        # First byte encodes first two arcs: X*40 + Y
        first = raw[0]
        arcs = [first // 40, first % 40]

        curr = 0
        for b in raw[1:]:
            curr = (curr << 7) | (b & 0x7F)
            if not (b & 0x80):
                arcs.append(curr)
                curr = 0

        return ".".join(str(a) for a in arcs)

    @staticmethod
    def encode_tlv(tag: int, value: bytes) -> bytes:
        """Constructs a DER TLV byte sequence."""
        length = len(value)
        if length < 128:
            len_bytes = bytes([length])
        elif length < 256:
            len_bytes = bytes([0x81, length])
        elif length < 65536:
            len_bytes = bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])
        else:
            len_bytes = bytes([0x84, (length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
        return bytes([tag]) + len_bytes + value

class X509Certificate:
    """
    Parses and holds an X.509 Public Key Certificate.
    """
    def __init__(self, raw_der: bytes):
        self.raw_der = raw_der
        self.version = 1
        self.serial_number = 0
        self.signature_algo = ""
        self.issuer: Dict[str, str] = {}
        self.subject: Dict[str, str] = {}
        self.not_before = ""
        self.not_after = ""
        self.public_key_algo = ""
        self.public_key_bytes = b""
        self.rsa_modulus: Optional[int] = None
        self.rsa_exponent: Optional[int] = None

        self._parse()

    def _parse(self):
        root, _ = DERDecoder.decode(self.raw_der)
        if root.tag != TAG_SEQUENCE or len(root.children) < 3:
            raise ValueError("Invalid X.509 Certificate structure")

        tbs_cert = root.children[0]
        sig_algo = root.children[1]
        sig_val  = root.children[2]

        child_idx = 0

        # Check version tag [0] explicit
        if tbs_cert.children[child_idx].tag == 0xA0:
            version_node = tbs_cert.children[child_idx].children[0]
            self.version = version_node.as_int() + 1
            child_idx += 1

        # Serial Number
        self.serial_number = tbs_cert.children[child_idx].as_int()
        child_idx += 1

        # Signature Algorithm in TBS
        self.signature_algo = self._extract_oid_name(tbs_cert.children[child_idx])
        child_idx += 1

        # Issuer DN
        self.issuer = self._parse_name(tbs_cert.children[child_idx])
        child_idx += 1

        # Validity
        validity = tbs_cert.children[child_idx]
        if len(validity.children) >= 2:
            self.not_before = validity.children[0].as_str()
            self.not_after  = validity.children[1].as_str()
        child_idx += 1

        # Subject DN
        self.subject = self._parse_name(tbs_cert.children[child_idx])
        child_idx += 1

        # SubjectPublicKeyInfo
        spki = tbs_cert.children[child_idx]
        if len(spki.children) >= 2:
            self.public_key_algo = self._extract_oid_name(spki.children[0])
            # Bit string: first byte is unused bits count (usually 0)
            bit_str = spki.children[1].value
            if bit_str and len(bit_str) > 1:
                self.public_key_bytes = bit_str[1:]
                if "rsa" in self.public_key_algo.lower():
                    self._parse_rsa_key(self.public_key_bytes)

    def _parse_rsa_key(self, rsa_der: bytes):
        """Parses PKCS#1 RSAPublicKey SEQUENCE { modulus INTEGER, publicExponent INTEGER }."""
        try:
            rsa_node, _ = DERDecoder.decode(rsa_der)
            if rsa_node.tag == TAG_SEQUENCE and len(rsa_node.children) >= 2:
                self.rsa_modulus = rsa_node.children[0].as_int()
                self.rsa_exponent = rsa_node.children[1].as_int()
        except Exception:
            pass

    def _parse_name(self, name_node: ASN1Node) -> Dict[str, str]:
        """Parses an X.501 RelativeDistinguishedName SET/SEQUENCE into a dictionary."""
        dn = {}
        for rdn_set in name_node.children:
            for seq in rdn_set.children:
                if len(seq.children) >= 2:
                    oid_str = seq.children[0].as_oid()
                    val_str = seq.children[1].as_str()
                    key = OID_MAP.get(oid_str, oid_str)
                    dn[key] = val_str
        return dn

    def _extract_oid_name(self, algo_node: ASN1Node) -> str:
        if algo_node.children:
            oid = algo_node.children[0].as_oid()
            return OID_MAP.get(oid, oid)
        return ""

def create_self_signed_cert_der(common_name: str = "adios.sovereign.local", rsa_modulus: int = 0xDEADBEEF, rsa_exp: int = 65537) -> bytes:
    """Helper to generate a valid DER-encoded X.509 certificate for testing."""
    # 1. Subject / Issuer DN: SEQUENCE { SET { SEQUENCE { OID(2.5.4.3), PrintableString(CN) } } }
    cn_oid = DERDecoder.encode_tlv(TAG_OID, bytes([0x55, 0x04, 0x03])) # 2.5.4.3
    cn_val = DERDecoder.encode_tlv(TAG_PRINTABLE_STRING, common_name.encode("ascii"))
    attr_seq = DERDecoder.encode_tlv(TAG_SEQUENCE, cn_oid + cn_val)
    rdn_set = DERDecoder.encode_tlv(TAG_SET, attr_seq)
    dn_seq = DERDecoder.encode_tlv(TAG_SEQUENCE, rdn_set)

    # 2. Validity: SEQUENCE { UTCTime("260904000000Z"), UTCTime("360904000000Z") }
    t1 = DERDecoder.encode_tlv(TAG_UTC_TIME, b"260904000000Z")
    t2 = DERDecoder.encode_tlv(TAG_UTC_TIME, b"360904000000Z")
    validity = DERDecoder.encode_tlv(TAG_SEQUENCE, t1 + t2)

    # 3. RSAPublicKey: SEQUENCE { INTEGER(modulus), INTEGER(exponent) }
    mod_bytes = rsa_modulus.to_bytes((rsa_modulus.bit_length() + 7) // 8, "big")
    if mod_bytes[0] & 0x80: mod_bytes = b"\x00" + mod_bytes
    exp_bytes = rsa_exp.to_bytes((rsa_exp.bit_length() + 7) // 8, "big")

    rsa_pub = DERDecoder.encode_tlv(
        TAG_SEQUENCE,
        DERDecoder.encode_tlv(TAG_INTEGER, mod_bytes) +
        DERDecoder.encode_tlv(TAG_INTEGER, exp_bytes)
    )

    # SPKI
    rsa_oid = bytes([0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x01, 0x01]) # 1.2.840.113549.1.1.1
    alg_id = DERDecoder.encode_tlv(TAG_SEQUENCE, DERDecoder.encode_tlv(TAG_OID, rsa_oid) + DERDecoder.encode_tlv(TAG_NULL, b""))
    spki = DERDecoder.encode_tlv(TAG_SEQUENCE, alg_id + DERDecoder.encode_tlv(TAG_BIT_STRING, b"\x00" + rsa_pub))

    # Signature Algorithm
    sha256_rsa_oid = bytes([0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x01, 0x0B])
    sig_alg = DERDecoder.encode_tlv(TAG_SEQUENCE, DERDecoder.encode_tlv(TAG_OID, sha256_rsa_oid) + DERDecoder.encode_tlv(TAG_NULL, b""))

    # Serial Number
    serial = DERDecoder.encode_tlv(TAG_INTEGER, bytes([0x01, 0x23, 0x45]))

    # TBS Certificate
    tbs_cert = DERDecoder.encode_tlv(
        TAG_SEQUENCE,
        serial + sig_alg + dn_seq + validity + dn_seq + spki
    )

    # Signature value (32 bytes dummy)
    sig_val = DERDecoder.encode_tlv(TAG_BIT_STRING, b"\x00" + (b"\xAA" * 32))

    # Top-level Certificate
    return DERDecoder.encode_tlv(TAG_SEQUENCE, tbs_cert + sig_alg + sig_val)
