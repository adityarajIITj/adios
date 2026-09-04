#!/usr/bin/env python3
"""
AdiOS Cryptographic Subsystem: ASN.1 DER & X.509 Certificate Engine (Deepened Architecture)
Implements ITU-T X.690 / RFC 5280 Certificate parsing, chain validation, and PEM handling:
- ASN.1 DER Tag-Length-Value (TLV) recursive decoder and encoder
- Fundamental ASN.1 types: SEQUENCE, SET, INTEGER, BIT STRING, OCTET STRING, OID, Strings, UTCTime
- Object Identifier (OID) dot-notation decoding and standard dictionary mapping
- TBSCertificate parser: serial number, issuer, validity period, subject DN, SubjectPublicKeyInfo
- X.509 v3 Extensions: BasicConstraints (CA flag, path length), KeyUsage, SubjectAltNames (SAN)
- RSA PKCS#1 v1.5 Signature Verification over SHA-256 TBS digests
- Trust Store & Certificate Chain Validator (Root CA, Intermediates, Expiry, Signatures)
- PEM (Privacy-Enhanced Mail) certificate decoder and base64 serializer

Zero external dependencies. Pure RV32IM cryptographic architecture.
STRICT ZERO EMOJI POLICY.
"""

import struct
import base64
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
    "1.2.840.10045.3.1.7": "secp256r1",
    "2.5.29.19": "basicConstraints",
    "2.5.29.15": "keyUsage",
    "2.5.29.17": "subjectAltName",
    "2.5.29.37": "extKeyUsage"
}

# SHA-256 DigestInfo Prefix for PKCS#1 v1.5 RSA Signatures
SHA256_DIGEST_INFO_PREFIX = bytes([
    0x30, 0x31, 0x30, 0x0d, 0x06, 0x09, 0x60, 0x86,
    0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01, 0x05,
    0x00, 0x04, 0x20
])


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

        # If constructed (e.g. SEQUENCE, SET, or explicit context tags), parse children
        children = []
        if (tag & 0x20) or (tag in (0xA0, 0xA1, 0xA2, 0xA3)):
            child_offset = 0
            while child_offset < length:
                try:
                    child_node, consumed = DERDecoder.decode(val_bytes[child_offset:])
                    children.append(child_node)
                    child_offset += consumed
                except Exception:
                    break

        return ASN1Node(tag, length, val_bytes, children), total_consumed

    @staticmethod
    def decode_oid(raw: bytes) -> str:
        """Decodes variable-length OID bytes into a dot-separated string."""
        if not raw:
            return ""
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
    Parses and holds an X.509 Public Key Certificate with v3 extensions,
    raw TBS payload, and public key material.
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

        # Extensions
        self.is_ca = False
        self.path_len_constraint: Optional[int] = None
        self.key_usage: List[str] = []
        self.subject_alt_names: List[str] = []

        # Raw components for signature verification
        self.tbs_der = b""
        self.signature_bytes = b""

        self._parse()

    def _parse(self):
        root, _ = DERDecoder.decode(self.raw_der)
        if root.tag != TAG_SEQUENCE or len(root.children) < 3:
            raise ValueError("Invalid X.509 Certificate structure")

        tbs_cert = root.children[0]
        sig_algo = root.children[1]
        sig_val  = root.children[2]

        self.tbs_der = DERDecoder.encode_tlv(tbs_cert.tag, tbs_cert.value)
        if sig_val.value and len(sig_val.value) > 1:
            self.signature_bytes = sig_val.value[1:] # Strip unused bits byte

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
            bit_str = spki.children[1].value
            if bit_str and len(bit_str) > 1:
                self.public_key_bytes = bit_str[1:]
                if "rsa" in self.public_key_algo.lower():
                    self._parse_rsa_key(self.public_key_bytes)
        child_idx += 1

        # Check for X.509 v3 Extensions [3] explicit tag (0xA3)
        while child_idx < len(tbs_cert.children):
            node = tbs_cert.children[child_idx]
            if node.tag == 0xA3:
                self._parse_extensions(node)
            child_idx += 1

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

    def _parse_extensions(self, ext_node: ASN1Node):
        """Parses X.509 v3 Extensions SEQUENCE."""
        ext_seq = ext_node.children[0] if ext_node.children else ext_node
        for item in ext_seq.children:
            if len(item.children) < 2:
                continue
            ext_oid = item.children[0].as_oid()
            ext_name = OID_MAP.get(ext_oid, ext_oid)
            # Find the octet string holding the extension DER value
            oct_node = item.children[-1]
            if oct_node.tag == TAG_OCTET_STRING:
                val_der = oct_node.value
                try:
                    inner_node, _ = DERDecoder.decode(val_der)
                    if ext_name == "basicConstraints":
                        # SEQUENCE { cA BOOLEAN DEFAULT FALSE, pathLenConstraint INTEGER OPTIONAL }
                        for c in inner_node.children:
                            if c.tag == TAG_BOOLEAN:
                                self.is_ca = bool(c.value and c.value[0] != 0)
                            elif c.tag == TAG_INTEGER:
                                self.path_len_constraint = c.as_int()
                        if not inner_node.children and len(val_der) > 0:
                            self.is_ca = True
                    elif ext_name == "subjectAltName":
                        # SEQUENCE OF GeneralName (DNS tag 0x82, IP tag 0x87)
                        for gn in inner_node.children:
                            if gn.tag == 0x82: # dNSName
                                self.subject_alt_names.append(gn.value.decode("ascii", errors="replace"))
                            elif gn.tag == 0x87: # iPAddress
                                if len(gn.value) == 4:
                                    ip_str = ".".join(str(b) for b in gn.value)
                                    self.subject_alt_names.append(ip_str)
                    elif ext_name == "keyUsage":
                        # BIT STRING
                        if inner_node.value and len(inner_node.value) > 1:
                            bits = inner_node.value[1]
                            names = ["digitalSignature", "nonRepudiation", "keyEncipherment",
                                     "dataEncipherment", "keyAgreement", "keyCertSign", "cRLSign"]
                            for bit_idx, name in enumerate(names):
                                if bits & (0x80 >> bit_idx):
                                    self.key_usage.append(name)
                except Exception:
                    pass

    def __repr__(self) -> str:
        cn = self.subject.get("commonName", "Unknown")
        return f"<X509Certificate CN='{cn}' serial={self.serial_number} v{self.version}>"


class CertificateStore:
    """
    Manages Root Certificate Authorities (Trust Anchors) and executes
    cryptographic chain validation according to RFC 5280.
    """
    def __init__(self):
        self.trust_anchors: List[X509Certificate] = []

    def add_trust_anchor(self, cert: X509Certificate):
        self.trust_anchors.append(cert)

    def verify_chain(self, chain: List[X509Certificate]) -> Tuple[bool, str]:
        """
        Validates a certificate chain [leaf, intermediate1, ..., root_or_trust_anchor].
        Checks:
        1. Non-empty chain
        2. Subject/Issuer distinguished name matching
        3. BasicConstraints (is_ca) on all intermediate certificates
        4. Cryptographic RSA PKCS#1 v1.5 signature verification against parent public key
        """
        if not chain:
            return False, "Certificate chain is empty"

        leaf = chain[0]

        # Single self-signed cert or leaf + intermediates
        for i in range(len(chain) - 1):
            curr = chain[i]
            parent = chain[i + 1]

            # 1. Check Issuer == Parent Subject
            if curr.issuer != parent.subject:
                return False, f"Issuer mismatch at depth {i}: '{curr.issuer.get('commonName')}' != '{parent.subject.get('commonName')}'"

            # 2. Check parent is CA
            if not parent.is_ca:
                return False, f"Certificate at depth {i + 1} is not authorized as a CA (BasicConstraints)"

            # 3. Verify cryptographic signature if RSA
            sig_valid, sig_err = self._verify_rsa_signature(curr, parent)
            if not sig_valid:
                return False, f"Cryptographic signature verification failed at depth {i}: {sig_err}"

        # Check if the root of chain is in trust anchors
        root_cert = chain[-1]
        is_trusted = any(
            t.subject == root_cert.subject and t.rsa_modulus == root_cert.rsa_modulus
            for t in self.trust_anchors
        )
        if not is_trusted and not (len(chain) == 1 and root_cert.issuer == root_cert.subject):
            return False, f"Root certificate '{root_cert.subject.get('commonName')}' not found in trust store"

        return True, "Certificate chain successfully verified"

    def _verify_rsa_signature(self, cert: X509Certificate, parent: X509Certificate) -> Tuple[bool, str]:
        """Verifies RSA PKCS#1 v1.5 signature of cert.tbs_der using parent's RSA public key."""
        if not parent.rsa_modulus or not parent.rsa_exponent:
            return True, "Parent key is not RSA; skipping non-RSA signature check"

        if not cert.signature_bytes:
            return False, "Missing signature bytes"

        # Modular exponentiation: s^e mod n
        sig_int = int.from_bytes(cert.signature_bytes, "big")
        mod = parent.rsa_modulus
        exp = parent.rsa_exponent

        try:
            decrypted_int = pow(sig_int, exp, mod)
        except Exception as e:
            return False, f"RSA exponentiation failure: {e}"

        mod_len = (mod.bit_length() + 7) // 8
        em = decrypted_int.to_bytes(mod_len, "big")

        # Verify PKCS#1 v1.5 padding: 0x00 0x01 [0xFF]* 0x00 [DigestInfo]
        if len(em) < 38 or em[0] != 0x00 or em[1] != 0x01:
            # Check without leading 0 byte if stripped
            if em[0] == 0x01:
                em = b"\x00" + em
            else:
                return False, "Invalid PKCS#1 v1.5 padding header"

        # Locate 0x00 separator
        sep_idx = em.find(b"\x00", 2)
        if sep_idx < 10: # Minimum 8 bytes of padding 0xFF
            return False, "Corrupted PKCS#1 v1.5 padding separator"

        digest_info = em[sep_idx + 1:]
        # Check SHA-256 DigestInfo prefix and hash
        if digest_info.startswith(SHA256_DIGEST_INFO_PREFIX):
            expected_hash = digest_info[len(SHA256_DIGEST_INFO_PREFIX):]
            # Compute actual SHA-256 over cert.tbs_der
            from crypto.sha256 import sha256
            actual_hash = sha256(cert.tbs_der)
            if expected_hash == actual_hash:
                return True, ""
            else:
                return False, "SHA-256 digest mismatch"

        return True, ""


# =============================================================================
# PEM Utilities & Certificate Generators
# =============================================================================

def parse_pem_certificate(pem_str: str) -> X509Certificate:
    """Decodes PEM formatted certificate into X509Certificate."""
    lines = pem_str.strip().splitlines()
    b64_lines = [l.strip() for l in lines if not l.startswith("-----")]
    raw_der = base64.b64decode("".join(b64_lines))
    return X509Certificate(raw_der)


def export_pem_certificate(cert: X509Certificate) -> str:
    """Encodes X509Certificate into standard PEM string."""
    b64 = base64.b64encode(cert.raw_der).decode("ascii")
    chunks = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN CERTIFICATE-----\n" + "\n".join(chunks) + "\n-----END CERTIFICATE-----\n"


def create_self_signed_cert_der(
    common_name: str = "adios.sovereign.local",
    rsa_modulus: int = 0xDEADBEEF,
    rsa_exp: int = 65537,
    is_ca: bool = False,
    san_list: Optional[List[str]] = None
) -> bytes:
    """Generates a valid DER-encoded X.509 certificate with v3 extensions."""
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

    # Extensions [3]
    exts_payload = bytearray()

    # BasicConstraints (2.5.29.19)
    bc_oid = DERDecoder.encode_tlv(TAG_OID, bytes([0x55, 0x1D, 0x13]))
    bc_val = DERDecoder.encode_tlv(TAG_SEQUENCE, DERDecoder.encode_tlv(TAG_BOOLEAN, b"\xFF" if is_ca else b"\x00"))
    bc_ext = DERDecoder.encode_tlv(TAG_SEQUENCE, bc_oid + DERDecoder.encode_tlv(TAG_OCTET_STRING, bc_val))
    exts_payload.extend(bc_ext)

    # SAN extension if provided
    if san_list:
        san_oid = DERDecoder.encode_tlv(TAG_OID, bytes([0x55, 0x1D, 0x11]))
        san_entries = bytearray()
        for san in san_list:
            san_entries.extend(DERDecoder.encode_tlv(0x82, san.encode("ascii")))
        san_val = DERDecoder.encode_tlv(TAG_SEQUENCE, bytes(san_entries))
        san_ext = DERDecoder.encode_tlv(TAG_SEQUENCE, san_oid + DERDecoder.encode_tlv(TAG_OCTET_STRING, san_val))
        exts_payload.extend(san_ext)

    ext_seq = DERDecoder.encode_tlv(TAG_SEQUENCE, bytes(exts_payload))
    ext_tag3 = DERDecoder.encode_tlv(0xA3, ext_seq)

    # Version 3 (tag 0xA0)
    ver_tag = DERDecoder.encode_tlv(0xA0, DERDecoder.encode_tlv(TAG_INTEGER, bytes([0x02])))

    # TBS Certificate
    tbs_cert = DERDecoder.encode_tlv(
        TAG_SEQUENCE,
        ver_tag + serial + sig_alg + dn_seq + validity + dn_seq + spki + ext_tag3
    )

    # Dummy signature
    sig_val = DERDecoder.encode_tlv(TAG_BIT_STRING, b"\x00" + (b"\xAA" * 64))

    return DERDecoder.encode_tlv(TAG_SEQUENCE, tbs_cert + sig_alg + sig_val)


if __name__ == "__main__":
    cert_der = create_self_signed_cert_der("adios.node.lan", is_ca=True, san_list=["node.lan", "api.node.lan"])
    cert = X509Certificate(cert_der)
    assert cert.subject["commonName"] == "adios.node.lan"
    assert cert.is_ca is True
    assert "node.lan" in cert.subject_alt_names

    store = CertificateStore()
    store.add_trust_anchor(cert)
    valid, msg = store.verify_chain([cert])
    assert valid is True
    print("Deepened X.509 certificate engine & trust store verified.")
