# persistent-interactive-ai-browser-agents

Persistent Interactive AI Browser Agents

## Open a page in a cloud desktop and watch it

`open_page.py` starts one [E2B](https://e2b.dev) desktop sandbox, opens a page in its browser, and prints a live link
to the sandbox's screen. It also saves a screenshot and a summary to `out/`.

```sh
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env          # then put your E2B_API_KEY in .env
.venv/bin/python open_page.py
```

Open the printed **Live view** link in any browser to see the sandbox's screen. Press Enter to stop the sandbox. If
you don't, E2B kills it at the hard timeout (5 minutes by default). Every run is a paid sandbox, billed per second; a
5-minute run costs about a cent.

| Option | What it does |
|---|---|
| `--url URL` | The page to open (default `https://www.reddit.com/`) |
| `--browser NAME` | Open it in a specific app: `google-chrome` or `firefox-esr` (default: the sandbox's default browser) |
| `--control` | The live link accepts your mouse and keyboard, not just viewing |
| `--hold SECONDS` | Keep it up this long instead of waiting for Enter |
| `--timeout SECONDS` | Hard timeout (default 300) |
| `--out DIR` | Where `desktop.png` and `summary.json` go (default `out/`) |

The live link contains the stream's password. Keep it private: whoever holds it can watch the desktop, and could take
control, until the sandbox stops. It is printed to the terminal only and never saved.

### What the sandbox is

E2B's `desktop` template: Ubuntu 22.04 with an XFCE desktop at 1024×768. Firefox ESR is the default browser, and
Google Chrome, VS Code and LibreOffice are also installed. Each run prints the real OS, CPU, memory and browsers as the
sandbox reports them.

### Reddit says "You've been blocked by network security"

Reddit blocks logged-out visitors coming from cloud data-center IP addresses, which is where E2B sandboxes run. The
routes Reddit allows are logging in (run with `--control` and use the live link) or its developer API.

E2B can also send a sandbox's outbound traffic through your own SOCKS5 proxy, set at creation with
`Sandbox.create(network={"egress_proxy": {"address": "host:port", "username": ..., "password": ...}})`. Only TCP goes
through the proxy; UDP, including HTTP/3, leaves directly. Routing around Reddit's block this way likely breaks
Reddit's terms.
