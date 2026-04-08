#!/usr/bin/env python3
"""
dynamic_dns.py — Keep maez.live pointed at this machine's public IP.
Runs every 5 minutes via cron. Uses Cloudflare API.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, '/home/rohit/maez')
from dotenv import load_dotenv
load_dotenv('/home/rohit/maez/config/.env')

ZONE_ID = os.environ.get('CLOUDFLARE_ZONE_ID', '')
API_TOKEN = os.environ.get('CLOUDFLARE_API_TOKEN', '')
DOMAIN = 'maez.live'
RECORD_TYPE = 'A'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('dns')


def get_public_ip() -> str:
    req = urllib.request.Request('https://api.ipify.org', headers={'User-Agent': 'Maez/1.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode().strip()


def cf_request(method: str, path: str, data: dict = None) -> dict:
    url = f'https://api.cloudflare.com/client/v4{path}'
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': f'Bearer {API_TOKEN}',
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_dns_record() -> tuple:
    """Returns (record_id, current_ip) or (None, None)."""
    result = cf_request('GET', f'/zones/{ZONE_ID}/dns_records?type={RECORD_TYPE}&name={DOMAIN}')
    records = result.get('result', [])
    if records:
        return records[0]['id'], records[0]['content']
    return None, None


def update_dns_record(record_id: str, ip: str):
    cf_request('PUT', f'/zones/{ZONE_ID}/dns_records/{record_id}', {
        'type': RECORD_TYPE,
        'name': DOMAIN,
        'content': ip,
        'ttl': 300,
        'proxied': False,
    })


def create_dns_record(ip: str):
    cf_request('POST', f'/zones/{ZONE_ID}/dns_records', {
        'type': RECORD_TYPE,
        'name': DOMAIN,
        'content': ip,
        'ttl': 300,
        'proxied': False,
    })


def main():
    if not ZONE_ID or not API_TOKEN:
        logger.error('[DNS] CLOUDFLARE_ZONE_ID or CLOUDFLARE_API_TOKEN not set')
        return

    try:
        current_ip = get_public_ip()
        record_id, dns_ip = get_dns_record()

        if dns_ip == current_ip:
            return  # No change, silent

        if record_id:
            update_dns_record(record_id, current_ip)
            logger.info('[DNS] IP changed from %s to %s — record updated', dns_ip, current_ip)
        else:
            create_dns_record(current_ip)
            logger.info('[DNS] Created A record for %s → %s', DOMAIN, current_ip)

    except Exception as e:
        logger.error('[DNS] Update failed: %s', e)


if __name__ == '__main__':
    main()
