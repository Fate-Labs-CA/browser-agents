#!/usr/bin/env python3
"""Open a web page in an E2B desktop sandbox and watch it live.

Starts one E2B desktop sandbox, opens the page in its browser, prints a live link to its desktop, saves a screenshot
and what the machine is (OS, size, browsers), then keeps the sandbox up until you press Enter or Ctrl-C, or until the
hard timeout ends it. The sandbox is always killed, and E2B kills it at the timeout even if this script crashes.

    python open_page.py                                    # reddit.com, view-only live link, 5-minute hard timeout
    python open_page.py --url https://example.com/ --browser google-chrome --control --hold 60
    python open_page.py --proxy                            # traffic leaves through the SOCKS5 proxy in .env

Needs E2B_API_KEY in the environment or in .env. Every run starts a paid sandbox, billed per second while it runs.

The live link is printed to this terminal and nowhere else. It carries the stream's password, so whoever holds it can
watch the desktop until the sandbox stops. View-only is a setting of the viewer page, not enforced by the server, so a
holder could also take control.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import sys
import time

from dotenv import load_dotenv
from e2b_desktop import Sandbox

# E2B's published usage prices (https://e2b.dev/pricing, read 2026-11-11), for a rough cost estimate only.
PRICE = {'vcpu_second': 0.000014, 'gib_second': 0.0000045}

# One command, key=value lines: what the machine is, before anything is opened.
FACTS = r'''
. /etc/os-release 2>/dev/null; echo "os=$PRETTY_NAME"
echo "kernel=$(uname -r)"
echo "cpus=$(nproc)"
echo "memory_mb=$(free -m | awk '/^Mem:/{print $2}')"
echo "desktop_sessions=$(ls /usr/share/xsessions 2>/dev/null | sed 's/\.desktop$//' | tr '\n' ' ')"
echo "https_handler=$(xdg-mime query default x-scheme-handler/https 2>/dev/null)"
echo "browsers=$(for b in google-chrome firefox-esr firefox chromium chromium-browser; do command -v $b >/dev/null && printf '%s ' $b; done)"
'''
RUNNING = "ps -eo comm= | grep -oE 'chrome|firefox|chromium' | sort -u | tr '\\n' ' '"
TITLE = 'xdotool getactivewindow getwindowname 2>/dev/null || true'


# E2B tunnels only TCP through the proxy; UDP leaves the sandbox directly. HTTP/3 runs over UDP, so with a proxy the
# browsers must not use it, or some traffic would come from E2B's own address. Browser policies, written as root.
NO_HTTP3 = r'''
set -e
ff='{"policies": {"Preferences": {"network.http.http3.enable": {"Value": false, "Status": "locked"}}}}'
mkdir -p /etc/firefox/policies /usr/lib/firefox-esr/distribution /etc/opt/chrome/policies/managed
echo "$ff" > /etc/firefox/policies/policies.json
echo "$ff" > /usr/lib/firefox-esr/distribution/policies.json
echo '{"QuicAllowed": false}' > /etc/opt/chrome/policies/managed/no-quic.json
'''


def proxy_settings() -> dict:
    """E2B's egress proxy from .env: a SOCKS5 proxy, e.g. an Oxylabs ISP IP (isp.oxylabs.io:8001 is the first IP)."""
    missing = [n for n in ('OXYLABS_PROXY_ADDRESS', 'OXYLABS_PROXY_USERNAME', 'OXYLABS_PROXY_PASSWORD') if not os.environ.get(n)]
    if missing:
        raise SystemExit(f'--proxy needs {", ".join(missing)} in .env')
    return {'address': os.environ['OXYLABS_PROXY_ADDRESS'], 'username': os.environ['OXYLABS_PROXY_USERNAME'],
            'password': os.environ['OXYLABS_PROXY_PASSWORD']}


def exit_ip(desktop: Sandbox) -> dict:
    """The address the sandbox's traffic leaves from, as the outside world sees it."""
    out = desktop.commands.run('curl -sS --max-time 20 https://ipinfo.io/json || true', timeout=30).stdout
    try:
        info = json.loads(out)
    except ValueError:
        return {'error': out[:200]}
    return {k: info.get(k) for k in ('ip', 'city', 'region', 'country', 'org')}


def facts(desktop: Sandbox) -> dict:
    lines = desktop.commands.run(FACTS, timeout=20).stdout.splitlines()
    return {name: value.strip() for name, _, value in (line.partition('=') for line in lines) if name}


def wait_for_stop(deadline: float, hold: float | None) -> str:
    """Keep the sandbox up: `hold` seconds, or until Enter on a terminal, never past the deadline. Says why it ended."""
    left = max(0.0, deadline - time.time() - 2)
    if hold is not None:
        time.sleep(min(hold, left))
        return f'held {min(hold, left):.0f}s'
    if not sys.stdin.isatty():
        return 'no terminal to wait on; pass --hold SECONDS to keep it up'
    print(f'Press Enter to stop it. It stops itself at {time.strftime("%H:%M:%S", time.localtime(deadline))}.', flush=True)
    ready, _, _ = select.select([sys.stdin], [], [], left)
    if ready:
        sys.stdin.readline()
        return 'Enter pressed'
    return 'reached the hard timeout'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--url', default='https://www.reddit.com/')
    parser.add_argument('--out', type=Path, default=Path('out'), help='where the screenshot and summary go')
    parser.add_argument('--browser', help="a desktop app to open it in ('google-chrome', 'firefox-esr'); "
                                          "default: the sandbox's default browser, via xdg-open")
    parser.add_argument('--control', action='store_true', help='the live link takes mouse and keyboard too, not just viewing')
    parser.add_argument('--hold', type=float, help='keep it up this many seconds instead of waiting for Enter')
    parser.add_argument('--timeout', type=int, default=300, help='hard timeout, seconds; E2B kills the sandbox then')
    parser.add_argument('--proxy', action='store_true',
                        help='send the sandbox\'s traffic through the SOCKS5 proxy in .env (OXYLABS_PROXY_*)')
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get('E2B_API_KEY'):
        print('E2B_API_KEY is not set. Put it in .env (see .env.example) or the environment.', file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    record: dict = {'url': args.url, 'browser_asked': args.browser or 'default (xdg-open)'}
    began = time.time()
    deadline = began + args.timeout
    desktop = None
    try:
        network = None
        if args.proxy:
            network = {'egress_proxy': proxy_settings()}
            record['proxy'] = network['egress_proxy']['address']  # never the username or password
        desktop = Sandbox.create(timeout=args.timeout, allow_internet_access=True, metadata={'purpose': 'open page'},
                                 network=network)
        record.update({'sandbox_id': desktop.sandbox_id, 'create_seconds': round(time.time() - began, 2),
                       'machine': facts(desktop)})
        print(json.dumps({'sandbox': desktop.sandbox_id, 'machine': record['machine']}, indent=2), flush=True)
        if args.proxy:
            desktop.commands.run(NO_HTTP3, user='root', timeout=20)
            record['exit_ip'] = exit_ip(desktop)
            print(json.dumps({'exit_ip': record['exit_ip']}, indent=2), flush=True)
        if args.browser:
            desktop.launch(args.browser, args.url)
        else:
            desktop.open(args.url)
        desktop.stream.start(require_auth=True)
        link = desktop.stream.get_url(view_only=not args.control, auth_key=desktop.stream.get_auth_key())
        print(f'\nLive view ({"control" if args.control else "view-only"}; keep this link private):\n{link}\n', flush=True)
        time.sleep(min(10, max(0.0, deadline - time.time() - 5)))  # let the page load before the screenshot
        record['browser_running'] = desktop.commands.run(RUNNING, timeout=10).stdout.split()
        record['window_title'] = desktop.commands.run(TITLE, timeout=10).stdout.strip()
        (args.out / 'desktop.png').write_bytes(bytes(desktop.screenshot()))
        record['screenshot'] = str(args.out / 'desktop.png')
        print(json.dumps({k: record[k] for k in ('browser_running', 'window_title', 'screenshot')}, indent=2), flush=True)
        record['ended_because'] = wait_for_stop(deadline, args.hold)
    except KeyboardInterrupt:
        record['ended_because'] = 'Ctrl-C'
    except Exception as exc:  # noqa: BLE001 - report what failed; the finally still kills the sandbox
        record['error'] = f'{type(exc).__name__}: {str(exc)[:300]}'
    finally:
        if desktop is not None:
            try:
                desktop.kill()
                record['killed'] = True
            except Exception as exc:  # noqa: BLE001 - E2B's hard timeout ends it anyway
                record['killed'] = f'kill failed ({type(exc).__name__}); E2B ends it at the timeout'
            seconds = min(time.time() - began, args.timeout)
            machine = record.get('machine', {})
            try:
                rate = int(machine['cpus']) * PRICE['vcpu_second'] + int(machine['memory_mb']) / 1024 * PRICE['gib_second']
                record['usd_estimate'] = round(rate * seconds, 4)
            except (KeyError, ValueError):
                pass
            record['seconds'] = round(seconds, 1)
    (args.out / 'summary.json').write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    return 1 if 'error' in record else 0


if __name__ == '__main__':
    raise SystemExit(main())
