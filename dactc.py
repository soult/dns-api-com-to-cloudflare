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

    def _parse_zone_file(self, fileobj):
        records = []

        for line in fileobj:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            typ, parts = line[0], line[1:].split(":")

            record = {"name": parts.pop(0)}
            records.append(record)

            if typ == "+":
                record.update({
                    "type": "A",
                    "content": parts.pop(0),
                })
            elif typ == "6":
                addr = parts.pop(0)
                addr = ":".join([addr[i:(i + 4)] for i in range(0, 32, 4)])
                record.update({
                    "type": "AAAA",
                    "content": addr,
                })
            elif typ == "C":
                record.update({
                    "type": "CNAME",
                    "content": parts.pop(0)
                })
            elif typ == "@":
                record.update({
                    "type": "MX",
                    "content": parts.pop(0),
                    "priority": int(parts.pop(0)),
                })
            elif typ == "T":
                content = parts.pop(0)
                assert content[0] == '"'
                while not content.endswith('"'):
                    content += ":" + parts.pop(0)
                record.update({
                    "type": "TXT",
                    "content": content[1:-1],
                })

            if len(parts) > 0:
                record["ttl"] = int(parts.pop(0))
            else:
                record["ttl"] = 1

        return records

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

    def compare_records(self, a, b):
        if a["type"] != b["type"]:
            return False
        if a["name"] != b["name"]:
            return False
        if a["type"] == "AAAA":
            a_addr = ipaddress.ip_address(a["content"])
            b_addr = ipaddress.ip_address(b["content"])
            if a_addr != b_addr:
                return False
        elif a["type"] == "MX":
            if a["content"] != b["content"]:
                return False
            if a["priority"] != b["priority"]:
                return False
        else:
            if a["content"] != b["content"]:
                return False
        if a["ttl"] != b["ttl"]:
            return False
        if a.get("proxied", False) != b.get("proxied", False):
            return False
        return True

    def sync(self):
        for entry in os.listdir(self.args.zones_directory):
            if entry.startswith("."):
                continue

            zones = self.cloudflare.zones.get(params={"name": entry.lower()})
            if zones:
                zone = zones[0]
            else:
                if self.args.dry_run:
                    print("--dry-run: Not creating zone %s" % entry)
                    continue
                zone = self.cloudflare.zones.post(data={"name": entry.lower(), "jump_start": False})

            cf_records = self.cloudflare.zones.dns_records.get(zone["id"])
            with open(self._zone_file(zone), "r") as fileobj:
                local_records = self._parse_zone_file(fileobj)

            # Find matches
            remaining_local_records = []
            for lrecord in local_records:
                match = False
                remaining_cf_records = []
                for cfrecord in cf_records:
                    if self.compare_records(lrecord, cfrecord):
                        match = True
                    else:
                        remaining_cf_records.append(cfrecord)
                if not match:
                    remaining_local_records.append(lrecord)
                cf_records = remaining_cf_records
            local_records = remaining_local_records

            # Delete remaining CF records
            for cfrecord in cf_records:
                if self.args.dry_run:
                    print("--dry-run: Not deleting record %s %s" % (cfrecord["name"], cfrecord["type"]))
                    continue
                self.cloudflare.zones.dns_records.delete(zone["id"], cfrecord["id"])

            # Send remaining local records
            for lrecord in local_records:
                if self.args.dry_run:
                    print("--dry-run: Not sending record %s %s" % (lrecord["name"], lrecord["type"]))
                    continue
                self.cloudflare.zones.dns_records.post(zone["id"], data=lrecord)

    def main(self):
        self.parse_args()
        self.cloudflare = CloudFlare.CloudFlare(self.args.email, self.args.api_key)

        if self.args.action == "fetch":
            self.fetch()
        elif self.args.action == "sync":
            self.sync()


if __name__ == "__main__":
    DnsApiComToCloudflare().main()
