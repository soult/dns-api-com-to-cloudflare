#!/usr/bin/env python

import argparse
import CloudFlare
import ipaddress
import os.path


class DnsApiComToCloudflare(object):

    RECORD_FORMAT = {
        "A": "+{name}:{content}",
        "AAAA": "6{name}:{content_modified}",
        "CNAME": "C{name}:{content}",
        "MX": "@{name}:{content}:{priority}",
        "TXT": "T{name}:\"{content}\"",
    }

    def parse_args(self):
        parser = argparse.ArgumentParser(
            description="Synchronize local zone files with Cloudflare")

        parser.add_argument(
            "--zones-directory",
            help="Directory with zone files",
            default="./zones"
        )

        group = parser.add_argument_group('Cloudflare')
        group.add_argument(
            "--email",
            required=True,
            help="Cloudflare account e-mail address"
        )
        group.add_argument(
            "--api-key",
            required=True,
            help="Cloudflare account API key"
        )

        subparsers = parser.add_subparsers(dest="action", help="Action")
        subparsers.required = True

        parser_fetch = subparsers.add_parser("fetch", help="Fetch records")
        parser_fetch.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing files",
        )

        parser_sync = subparsers.add_parser("sync", help="Synchronize records")
        parser_sync.add_argument(
            "--dry-run",
            action="store_true",
            help="Dry-run (do not change any zone data on CloudFlare)"
        )

        self.args = parser.parse_args()

        if not os.path.isdir(self.args.zones_directory):
            parser.error("--zones-directory does not exist")

    def _zone_file(self, zone):
        return os.path.join(self.args.zones_directory, zone["name"])

    def fetch(self):
        for zone in self.cloudflare.zones.get():
            open_mode = "w" if self.args.overwrite else "x"
            with open(self._zone_file(zone), open_mode) as fileobj:
                fileobj.write("# Zone ID:   %s\n" % zone["id"])
                fileobj.write("# Zone Name: %s\n\n" % zone["name"])

                for record in self.cloudflare.zones.dns_records.get(zone["id"]):
                    fileobj.write("# Record ID: %s\n" % record["id"])
                    if record["proxied"]:
                        fileobj.write("# Proxied\n#")
                    if record["type"] == "AAAA":
                        addr = ipaddress.ip_address(record["content"])
                        record["content_modified"] = addr.exploded.replace(":", "")

                    if record["type"] in self.RECORD_FORMAT:
                        fileobj.write(self.RECORD_FORMAT[record["type"]].format(**record))
                    else:
                        print(record)

                    if record["ttl"] == 1:
                        fileobj.write("\n\n")
                    else:
                        fileobj.write(":%i\n\n" % record["ttl"])

    def main(self):
        self.parse_args()
        self.cloudflare = CloudFlare.CloudFlare(self.args.email, self.args.api_key)

        if self.args.action == "fetch":
            self.fetch()
        elif self.args.action == "sync":
            raise NotImplementedError()


if __name__ == "__main__":
    DnsApiComToCloudflare().main()
