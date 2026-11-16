# persistent-interactive-ai-browser-agents
Persistent Interactive AI Browser Agents

## Open a page in a cloud desktop and watch it

`open_page.py` starts one [E2B](https://e2b.dev) desktop sandbox, opens a page in its browser, and prints a live link
to the sandbox's screen. It also saves a screenshot and a summary to `out/`.

### Setup

```sh
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env          # then fill in the keys below
```

`.env` is git-ignored. Never commit it.

| Variable | What it is |
|---|---|
| `E2B_API_KEY` | Your E2B key, from https://e2b.dev/dashboard |
| `OXYLABS_PROXY_ADDRESS` | Only for `--proxy`. `isp.oxylabs.io:8001` is your first Oxylabs ISP IP, `:8002` the second, and so on |
| `OXYLABS_PROXY_USERNAME` | Only for `--proxy`. Your Oxylabs proxy user, with the `user-` prefix (e.g. `user-isp_xxxxxxxx`) |
| `OXYLABS_PROXY_PASSWORD` | Only for `--proxy`. That proxy user's password |

### Run it

```sh
.venv/bin/python open_page.py                        # reddit.com, view-only, 5-minute limit
.venv/bin/python open_page.py --proxy                # same, through your proxy IP
.venv/bin/python open_page.py --proxy --control      # through the proxy, and you can click and type
.venv/bin/python open_page.py --proxy --control --timeout 900   # same, for up to 15 minutes
```

1. If you used `--proxy`, check the `exit_ip` line it prints. It should show your proxy's IP and country, not E2B's.
2. Open the printed **Live view** link in any browser to see the sandbox's screen. With `--control`, your mouse and
   keyboard work in it, so you can log in to sites.
3. Press Enter in the terminal to stop the sandbox. If you don't, E2B kills it at the time limit.

Every run is a fresh sandbox, so logins don't carry over between runs. Every run is also a paid sandbox, billed per
second only while it runs; a 5-minute run costs about a cent.

| Option | What it does |
|---|---|
| `--url URL` | The page to open (default `https://www.reddit.com/`) |
| `--proxy` | Send the sandbox's traffic through the SOCKS5 proxy in `.env` |
| `--control` | The live link accepts your mouse and keyboard, not just viewing |
| `--browser NAME` | Open it in a specific app: `google-chrome` or `firefox-esr` (default: the sandbox's default browser) |
| `--hold SECONDS` | Keep it up this long instead of waiting for Enter |
| `--timeout SECONDS` | Time limit; E2B kills the sandbox then (default 300) |
| `--out DIR` | Where `desktop.png` and `summary.json` go (default `out/`) |

The live link contains the stream's password. Keep it private: whoever holds it can watch the desktop, and could take
control, until the sandbox stops. It is printed to the terminal only and never saved.

### The proxy

With `--proxy`, E2B sends all of the sandbox's outgoing TCP traffic through your SOCKS5 proxy, from outside the
sandbox, so nothing inside needs proxy settings and nothing inside can get around it. The script also:

- turns off HTTP/3 in Firefox and Chrome inside the sandbox, because E2B doesn't send UDP (which HTTP/3 uses) through
  the proxy, so that traffic would otherwise leave from E2B's own address;
- prints the address the sandbox's traffic actually comes out from (`exit_ip`), so you can check it.

The proxy's username and password are never printed or saved to `summary.json`.

E2B only accepts SOCKS5 proxies, not HTTP ones.

**Current proxy: Oxylabs ISP Proxies, "Pay per IP" (shared).**

- $1.50 per IP per month, buy as few as 1; about $1.40 each at 50+. Dedicated IPs start at $3.30 each.
- The IP is static: port 8001 always uses the same IP. Port 8000 rotates between your IPs, so don't use it.
- No traffic charges. Fair use: past about 50 GB per IP per month on shared IPs, connections at once on that IP drop
  from 100 to 10. Normal browsing uses far less.
- "Shared" means up to 3 Oxylabs customers can use the same IP.
- Manage it, see usage, change an IP's location, or reset the password at https://dashboard.oxylabs.io.

Test the proxy from your own machine:

```sh
set -a; . ./.env; set +a
curl -x "socks5h://$OXYLABS_PROXY_ADDRESS" -U "$OXYLABS_PROXY_USERNAME:$OXYLABS_PROXY_PASSWORD" https://ip.oxylabs.io/location
```

### What the sandbox is

E2B's `desktop` template: Ubuntu 22.04 with an XFCE desktop at 1024×768. Firefox ESR is the default browser, and
Google Chrome, VS Code and LibreOffice are also installed. Each run prints the real OS, CPU, memory and browsers as the
sandbox reports them.

## Background and decisions (Q&A)

Notes from setting this up, November 2026. Prices and provider facts change; re-check before relying on them.

### Why does Reddit block the sandbox?

Reddit blocks logged-out visitors whose traffic comes from cloud data centers, which is where E2B sandboxes run (their
outgoing addresses rotate within cloud ranges). A brand-new browser with no cookies or history looks even more like a
bot. Your home browser gets through because it has a residential ISP address. You'd likely see the same block from
AWS, Google Cloud or any other cloud machine. The block page itself offers the allowed ways in: log in, or use a
developer token (Reddit's API).

### Why can OpenAI and Google read Reddit when an AI agent can't?

They pay for it. Reddit signed data-licensing deals with Google and OpenAI in 2024 (reported at around $60M a year;
that figure isn't confirmed), which give official access to Reddit's data instead of scraping the website.

Anthropic has no such deal: Reddit sued Anthropic in June 2025, saying Claude was trained on Reddit content without a
license. Anthropic disputes that; as of November 2026 the case is still in court. Reddit blocks Anthropic's tools
outright, so Claude couldn't search or read Reddit while researching this project either.

Sources: [TechCrunch](https://techcrunch.com/?p=3015235),
[Daily Journal](https://dailyjournal.com/article/390586-reddit-data-scraping-suit-against-anthropic-back-to-state-court),
[Legal.io](https://www.legal.io/blog/5686080/Reddit-Sues-Anthropic-for-Allegedly-Scraping-Content-to-Train-Claude-AI).

### Which proxy, and why Oxylabs?

The need: static ISP (residential) IPs, billed per IP rather than per GB, one IP per account, US and Canada, around
10 IPs to start, cheap and not dropping connections. A first research round compared about 25 providers. Its
double-check round was cut short, so treat these as unverified starting points:

| Provider | Price per IP (at 10 IPs, monthly) | US + Canada | Reliability evidence |
|---|---|---|---|
| **Oxylabs, shared "Pay per IP"** | **$1.50** ($1.40 at 50) | Yes | Adequate: fast in tests; one user-reported multi-day outage |
| Webshare, private (shared with 0–2 others) | $0.98 | Yes | Weak: 98.3% uptime on its own status page; auto-swaps IPs that go down |
| Webshare, dedicated | $2.52 | Yes | Weak |
| Proxiware | US $1.00, Canada $1.40–1.75 | Yes | Unknown: no independent tests |
| Bright Data, shared | $1.80 | Yes | Not enough recent data; its rules ban fake accounts and fake engagement |
| HypeProxies | $1.30 (25-IP minimum) | US only | Adequate: cleanest test record |
| Evomi | $1.00 shared / $2.50 private | US only | Adequate |

Avoid, based on evidence found: Decodo (its own status page showed 20–36 hour outages of US static IPs, Oct–Nov 2026),
Rayobyte (18 of 100 IPs offline for a whole Proxyway test), IPRoyal (94.75% success in Proxyway's test), and
Proxy-Seller, Proxy-Cheap and Geonix (recent user reports of ISP IPs dying).

Oxylabs won on price for both countries plus the best available reliability evidence. Confirmed on its dashboard on
2026-11-15: shared IPs at $1.50 each, buyable one at a time, with 1,268 shared Canadian IPs in stock. Full notes and
sources: `research_notes/Cheap static ISP proxies US Canada/` (kept locally, not in the repo).

No independent test anywhere measured whether an IP stays up for days, or tested Canadian IPs, so watch the first
weeks yourself.

### Why does it have to be SOCKS5?

E2B grabs every outgoing connection from outside the sandbox and passes it through the proxy, so nothing inside needs
proxy settings. SOCKS5 is the standard protocol for passing along any kind of connection that way, so it's the only
kind E2B accepts. An HTTP proxy only handles web requests an app has been told to send to it. You could still use one
by setting it in the browser inside the sandbox, but then only that browser would use it and the password would sit
inside the sandbox.

### Is the traffic unlimited?

No traffic charges: the flat per-IP price covers it. Oxylabs' fair-use policy cuts connections at once from 100 to 10
on an IP past about 50 GB per month (shared) or 100 GB (dedicated). One account browsing Reddit uses far less.

### What does this cost?

- Oxylabs: $1.50 per IP per month. New accounts get $5 of free credit, enough for one IP for about three months.
- E2B: billed per second only while a sandbox runs; a 5-minute run is about a cent. `open_page.py` always stops the
  sandbox when you're done, and E2B kills it at the time limit if the script crashes.

### Reddit says "You've been blocked by network security"

Reddit blocks logged-out visitors coming from cloud data-center IP addresses, which is where E2B sandboxes run. Fixes:
run with `--proxy` so the traffic comes from a residential ISP address, and/or log in with `--control`. Reddit's
developer API is the route Reddit officially allows for automated access; routing around its block with a proxy may
break Reddit's terms.
