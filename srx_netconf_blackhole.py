#!/usr/bin/env python3
"""
srx_netconf_blackhole.py

Juniper SRX NETCONF automation for FastNetMon:
- ban:   add /32 discard static route
- unban: remove /32 discard static route


Examples:
  Ban (commit confirmed enabled by default):
    ./srx_netconf_blackhole.py ban --host 10.16.0.1 --user fastnetmon --ssh-key /root/.ssh/id_rsa --ip 10.16.64.8

  Ban (permanent until unban):
    ./srx_netconf_blackhole.py ban --host 10.16.0.1 --user fastnetmon --ssh-key /root/.ssh/id_rsa --ip 10.16.64.8 --no-commit-confirmed

  Unban (commit confirmed is always disabled internally):
    ./srx_netconf_blackhole.py unban --host 10.16.0.1 --user fastnetmon --ssh-key /root/.ssh/id_rsa --ip 10.16.64.8
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


def _ensure_ncclient_installed() -> None:
    """
    Attempt to import ncclient; if missing, try to install it.
    Uses subprocess without shell=True and without interactive prompts.
    """
    try:
        import ncclient  
        return
    except Exception:
        pass

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "ncclient",
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e:
        raise RuntimeError("pip not available to install dependencies (python -m pip failed).") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "Failed to auto-install ncclient. Install manually with: pip3 install ncclient"
        ) from e

    import ncclient 


_ensure_ncclient_installed()

from ncclient import manager  
from ncclient.transport.errors import (  
    AuthenticationError,
    SSHError,
    SessionCloseError,
)
from ncclient.xml_ import to_ele  


@dataclass(frozen=True)
class Options:
    action: str
    host: str
    port: int
    user: str
    password: Optional[str]
    ssh_key: Optional[str]
    ip: str
    timeout: int
    hostkey_verify: bool
    commit_confirmed: bool
    confirm_timeout: int


def _validate_ipv4(ip: str) -> str:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as e:
        raise ValueError(f"Invalid IP address: {ip}") from e
    if addr.version != 4:
        raise ValueError(f"Only IPv4 is supported in this script. Got: {ip}")
    return ip


def _build_set_line(action: str, ip: str) -> str:
    prefix = f"{ip}/32"
    if action == "ban":
        return f"set routing-options static route {prefix} discard"
    if action == "unban":
        return f"delete routing-options static route {prefix}"
    raise ValueError(f"Unknown action: {action}")


def _build_load_configuration_rpc(set_line: str) -> str:
    return f"""
<load-configuration action="set" format="text">
  <configuration-set><![CDATA[
{set_line}
]]></configuration-set>
</load-configuration>
""".strip()


def _static_discard_route_exists(m: manager.Manager, ip: str) -> bool:
    """
    Check if the exact discard route exists in running config using a narrow subtree filter.
    """
    prefix = f"{ip}/32"
    filter_xml = f"""
<filter>
  <configuration>
    <routing-options>
      <static>
        <route>
          <name>{prefix}</name>
          <discard/>
        </route>
      </static>
    </routing-options>
  </configuration>
</filter>
""".strip()
    reply = m.get_config(source="running", filter=to_ele(filter_xml))
    return prefix in str(reply)


def _connect_options(opts: Options) -> dict:
    kwargs = dict(
        host=opts.host,
        port=opts.port,
        username=opts.user,
        password=opts.password,
        timeout=opts.timeout,
        hostkey_verify=opts.hostkey_verify,
        device_params={"name": "junos"},
        allow_agent=False,
        look_for_keys=False,
    )

    if opts.ssh_key:
        kwargs["key_filename"] = opts.ssh_key
        if opts.password is None:
            kwargs.pop("password", None)

    return kwargs


def apply_change(opts: Options) -> str:
    """
    Apply ban/unban change. Returns:
      - "changed" if a commit was performed
      - "noop" if already in desired state
    """
    _validate_ipv4(opts.ip)

    commit_confirmed = opts.commit_confirmed if opts.action == "ban" else False

    set_line = _build_set_line(opts.action, opts.ip)
    rpc_xml = _build_load_configuration_rpc(set_line)

    with manager.connect(**_connect_options(opts)) as m:
        m.timeout = opts.timeout

        exists = _static_discard_route_exists(m, opts.ip)
        if opts.action == "ban" and exists:
            return "noop"
        if opts.action == "unban" and (not exists):
            return "noop"

        m.lock(target="candidate")
        try:
            m.dispatch(to_ele(rpc_xml))

            if commit_confirmed:
                m.commit(confirmed=True, timeout=opts.confirm_timeout)
            else:
                m.commit()
        finally:
            try:
                m.unlock(target="candidate")
            except Exception:
                pass

    return "changed"


def parse_args(argv: list[str]) -> Options:
    p = argparse.ArgumentParser(
        description="Ban/unban an IPv4 host on Juniper SRX via NETCONF using a /32 discard static route."
    )
    p.add_argument("action", choices=["ban", "unban"])
    p.add_argument("--host", required=True, help="SRX management IP/hostname.")
    p.add_argument("--port", type=int, default=830, help="NETCONF port (default: 830).")
    p.add_argument("--user", required=True, help="NETCONF username.")

    auth = p.add_mutually_exclusive_group(required=False)
    auth.add_argument("--password", help="NETCONF password (avoid in scripts; prefer SSH key).")
    auth.add_argument("--ssh-key", dest="ssh_key", help="Path to SSH private key (e.g. /root/.ssh/id_rsa).")

    p.add_argument("--ip", required=True, help="IPv4 address to ban/unban.")
    p.add_argument("--timeout", type=int, default=120, help="RPC wait timeout seconds (default: 120).")

    p.add_argument(
        "--hostkey-verify",
        action="store_true",
        help="Enable SSH host key verification (recommended).",
    )

    p.add_argument(
        "--commit-confirmed",
        dest="commit_confirmed",
        action="store_true",
        default=True,
        help="Enable commit confirmed for BAN (default). Forced OFF for UNBAN.",
    )
    p.add_argument(
        "--no-commit-confirmed",
        dest="commit_confirmed",
        action="store_false",
        help="Disable commit confirmed (use normal commit).",
    )
    p.add_argument(
        "--confirm-timeout",
        type=int,
        default=600,
        help="Timeout value passed to ncclient for confirmed commit workflow (default: 600).",
    )

    args = p.parse_args(argv)

    return Options(
        action=args.action,
        host=args.host,
        port=args.port,
        user=args.user,
        password=getattr(args, "password", None),
        ssh_key=getattr(args, "ssh_key", None),
        ip=args.ip,
        timeout=args.timeout,
        hostkey_verify=args.hostkey_verify,
        commit_confirmed=args.commit_confirmed,
        confirm_timeout=args.confirm_timeout,
    )


def main(argv: list[str]) -> int:
    try:
        opts = parse_args(argv)
        status = apply_change(opts)
        print(f"OK: {opts.action} {opts.ip} on {opts.host} ({status})")
        return 0

    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except AuthenticationError:
        print("ERROR: authentication failed", file=sys.stderr)
        return 10
    except SSHError as e:
        print(f"ERROR: SSH/transport error: {e}", file=sys.stderr)
        return 11
    except SessionCloseError as e:
        print(f"ERROR: NETCONF session closed unexpectedly: {e}", file=sys.stderr)
        return 12
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 13
    except Exception as e:
        print(f"ERROR: unexpected failure: {e}", file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))