# dns-api-com-to-cloudflare
Takes zonefiles made for [dns-api.com](https://dns-api.com/) and syncs them
with [Cloudflare](https://www.cloudflare.com/) DNS service. Note: Author of
this software is not affiliated with either company.

## Why?
To use the [simplified TinyDNS zone file
format](https://dns-api.com/docs/zone/) from dns-api.com with the free service
from Cloudflare.

## Requirements
* Python3
* [cloudflare-python](https://github.com/cloudflare/python-cloudflare)
* Cloudflare account/API access

## Run
```bash
    $ echo Fetching zone data from Cloudflare
    $ mkdir zones
    $ ./dactc.py --api-key=e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4 --email=user@example.com fetch
    $ vim zones/example.com
    $ echo Syncing changes to Cloudflare (dry-run - no changes)
    $ ./dactc.py --api-key=e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4 --email=user@example.com sync --dry-run
    $ echo Actually syncing changes
    $ ./dactc.py --api-key=e5e9fa1ba31ecd1ae84f75caaa474f3a663f05f4 --email=user@example.com sync
```
