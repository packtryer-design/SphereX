# Hosting Blink

The public site (Vercel) is static: it shows the catalog, search and About pages by itself. Images and spectra come from the Python API, which runs on **any team member's computer** and is reached through a free Cloudflare tunnel.

## Start hosting (any computer)

```bash
python scripts/host.py        # or: make host. Ctrl+C to stop
```

It prints something like:

```
[host 07:53:44] hosting. The public site now uses this computer. Ctrl+C to stop.
[host 07:53:44] direct link (works even without the public site): https://<random-words>.trycloudflare.com/?o=barnards-star
```

That's all. Within a few seconds the Vercel site uses this computer: no redeploy, no settings.

What `host.py` does:
1. **Starts the API** on port 8000, or reuses one already running there.
2. **Opens a Cloudflare quick tunnel**: a public https address, with no account needed. The first time, it downloads `cloudflared` into `.tools/` if it isn't installed.
3. **Publishes the address** as `endpoint.json` on the `api-endpoint` branch. The site reads that file on every visit (`apiBase()` in `web/js/api.js`) and checks the address is alive before using it.
4. **Watches the tunnel** every 30 s and reopens it if it drops, publishing the new address.
5. **On Ctrl+C, marks the server offline**, so visitors see "Blink's data server is offline right now" instead of an error. If another computer has started hosting since, it leaves that one alone.

## Requirements on the hosting computer

- **The repo**, cloned, with `git push` working (the address is published with a push to `api-endpoint`).
- **The API's Python dependencies.** See the README, "Run it".
- **A warm cache for the demo objects.** Otherwise the first visitor waits minutes for NASA's archive:
  ```bash
  python scripts/warm_cache.py barnards-star orion
  ```
  If `cache/demo/` is committed (Person A's A4), the API copies it in at startup and those objects work immediately.
- **Stay awake.** The computer must stay on, online and not asleep while hosting.

## Switching computers

Run `host.py` on the new computer. The **most recent** one to start wins, because it publishes its address over the old one. Then stop the old one with Ctrl+C: it sees it has been replaced and doesn't mark the server offline.

## Notes

- **The address changes every session.** That's how free quick tunnels work, and why it's published rather than written into the site. `?api=https://…` on any page link still overrides it, for testing.
- **The `api-endpoint` branch holds only that file**, plus a `vercel.json` that stops Vercel from trying to deploy the branch. It's force-pushed each time; don't merge it anywhere.
- **Visitors get the same data a local run gives.** The API is read-only for them, they can only reach what the site asks for, and CORS allows any origin to read.
- **A quick tunnel is for demos.** It has no uptime guarantee. For an always-on server, deploy the `Dockerfile` (Render, Fly.io, Hugging Face Spaces) and open the site with `?api=` pointing at it, or change `ENDPOINT_SOURCES` in `web/js/api.js`.
