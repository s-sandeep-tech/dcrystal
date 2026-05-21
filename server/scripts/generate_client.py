#!/usr/bin/env python3
import sys
import secrets
import argparse
import hashlib

def generate_client(client_id, client_name, custom_token=None):
    # 1. Generate or use custom token
    plain_token = custom_token if custom_token else f"dcrystal_{secrets.token_hex(16)}"
    
    # 2. Hash the plain token using SHA-256
    token_hash = hashlib.sha256(plain_token.encode('utf-8')).hexdigest()
    
    # 3. Format authorization bearer header example
    auth_header_value = f"Bearer {client_id}.{plain_token}"
    
    # 4. Generate SQL script
    sql_script = f"""-- Insert query for client: '{client_name}'
INSERT INTO thirdpartyapiclients (client_id, client_name, token_hash, is_active, created_at)
VALUES (
    '{client_id}',
    '{client_name}',
    '{token_hash}',
    TRUE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (client_id) 
DO UPDATE SET 
    client_name = EXCLUDED.client_name,
    token_hash = EXCLUDED.token_hash,
    is_active = EXCLUDED.is_active;"""

    print("=" * 70)
    print("🔑 THIRD-PARTY API CLIENT CREDENTIALS GENERATED SUCCESSFULLY")
    print("=" * 70)
    print(f"Client Name  : {client_name}")
    print(f"Client ID    : {client_id}")
    print(f"Plain Token  : {plain_token}")
    print("-" * 70)
    print("⚠️  IMPORTANT: Send the plain token below to the third party SECURELY.")
    print("   They must use it in their request header:")
    print(f"   Authorization: {auth_header_value}")
    print("-" * 70)
    print("💾 RUN THE FOLLOWING SQL SCRIPT IN YOUR PRODUCTION DATABASE (SHA-256 Hashed):")
    print("-" * 70)
    print(sql_script)
    print("=" * 70)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate third-party client tokens and SQL seed inserts.")
    parser.add_argument("--id", required=True, help="Unique Client ID (slug format, e.g. client-name-sync)")
    parser.add_argument("--name", required=True, help="Client Human Readable Name (e.g. 'Supplier Partner Inc')")
    parser.add_argument("--token", default=None, help="Optional specific plain-text token (auto-generated if omitted)")
    
    args = parser.parse_args()
    generate_client(args.id, args.name, args.token)
