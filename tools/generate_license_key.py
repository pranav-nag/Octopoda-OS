#!/usr/bin/env python3
"""
Synrix License Key Generator
==============================
Generate HMAC-signed license keys for customers.

THIS FILE IS NOT SHIPPED WITH THE PRODUCT.
Keep it private — it contains the signing secret.

Usage:
    python tools/generate_license_key.py --tier starter --email customer@example.com
    python tools/generate_license_key.py --tier pro --email team@company.com --expires-days 365
"""

import argparse
import json
import hmac
import hashlib
import base64
import time
import sys
import os

# Add SDK to path for tier definitions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python-sdk"))

from synrix.licensing import TIER_LIMITS, _get_verify_secret


def generate_key(tier: str, email: str, expires_days: int = 0) -> str:
    """Generate a signed license key."""
    limits = TIER_LIMITS[tier]

    payload = {
        "tier": tier,
        "max_agents": limits["max_agents"],
        "max_memories_per_agent": limits["max_memories_per_agent"],
        "iat": int(time.time()),
        "exp": int(time.time() + expires_days * 86400) if expires_days > 0 else 0,
        "sub": email,
    }

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).rstrip(b"=").decode()

    sig = hmac.new(
        _get_verify_secret(),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    return f"synrix-license-{payload_b64}.{sig_b64}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate Synrix license keys for customers"
    )
    parser.add_argument(
        "--tier",
        required=True,
        choices=["starter", "pro", "unlimited"],
        help="License tier",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Customer email address",
    )
    parser.add_argument(
        "--expires-days",
        type=int,
        default=0,
        help="Days until expiry (0 = never expires)",
    )
    args = parser.parse_args()

    key = generate_key(args.tier, args.email, args.expires_days)
    limits = TIER_LIMITS[args.tier]

    print()
    print(f"  Tier:     {args.tier}")
    print(f"  Email:    {args.email}")
    print(f"  Agents:   {'unlimited' if limits['max_agents'] == 0 else limits['max_agents']}")
    print(f"  Memories: {'unlimited' if limits['max_memories_per_agent'] == 0 else limits['max_memories_per_agent']}/agent")
    print(f"  Expires:  {'never' if args.expires_days == 0 else f'{args.expires_days} days'}")
    print()
    print(f"  License key:")
    print(f"  {key}")
    print()
    print(f"  Customer sets:")
    print(f"  SYNRIX_LICENSE_KEY={key}")
    print()


if __name__ == "__main__":
    main()
