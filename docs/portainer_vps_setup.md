# Portainer + VPS Exposure Guide

Run the Ticket Dashboard in a local Docker engine (managed by Portainer) and publish it securely through a VPS that already runs Traefik and Tailscale.

## 1. Prerequisites
- Local machine: Docker Engine >= 24, Portainer (CE/Business) with stack management rights, Tailscale client installed and logged into the same tailnet as the VPS.
- VPS: Linux host with Docker, Traefik (running via Docker or systemd), Tailscale client enrolled in the tailnet, and public IPv4/IPv6 connectivity.
- Domain: DNS control for a subdomain (for example `support.example.com`).
- Optional integrations: API keys and Google service account JSON (place it next to the compose file).

## 2. Build the image (outside Portainer)
Some Portainer agents cannot build images because they rely on BuildKit over HTTP/2. Build the image locally with Docker CLI before deploying the stack:
```bash
# From the repository root on the Portainer-managed host
docker build -t ticket-dashboard:latest .
```
Push the image to your private registry if Portainer runs on another node:
```bash
docker tag ticket-dashboard:latest registry.example.com/ticket-dashboard:latest
docker push registry.example.com/ticket-dashboard:latest
```
Update the compose file's `image:` reference to match the registry name if you push it.

## 3. Create the Portainer Stack
1. Ensure the repository (or the generated `docker-compose.portainer.yml`) is available to Portainer.
2. In Portainer go to **Stacks → Add stack → Web editor**.
3. Paste `docker-compose.portainer.yml` and adjust anything required (paths, image name, environment variables).
4. Provide environment variables:
   - Either add them inline in the stack editor or upload a `.env` file containing values for `HUBSPOT_API_KEY`, `LIVECHAT_PAT`, `GEMINI_API_KEY`, etc.
   - Leave values empty if you do not use an integration.
5. Persist important folders:
   - `tickets`, `uploads`, and `results` are bind-mounted; ensure those folders exist and the Docker user has write access.
   - Remove the `service_account_credentials.json` volume if Google Sheets export is not used.
6. Deploy the stack. Portainer pulls/uses the pre-built image and exposes port `8080` inside the container → `8080` on the host.

### Quick validation
- In Portainer, open **Logs** for the container; you should see `App imported successfully` from the Gunicorn startup.
- Visit `http://<local-host>:8080/health` to confirm the app is reachable inside your network.

## 4. Harden the container
- Set a strong `ADMIN_PASSWORD` before exposing the UI.
- Use Portainer's secret store for credentials when possible.
- Keep the bind-mounted data directories readable/writable only by the Docker group.

## 5. Route traffic through the VPS (Traefik + Tailscale)
Tailscale provides private connectivity between the local Portainer host and the VPS; Traefik terminates TLS and proxies traffic to the tailnet address of the dashboard container.

### 5.1 Ensure Tailscale connectivity
1. Install Tailscale on the local host (outside the container is simplest) and log in:
   ```bash
   sudo tailscale up --accept-dns=false --ssh
   ```
   Note the IPv4 tailnet address (example `100.101.102.103`). Pin it in the Tailscale admin console so it remains stable.
2. On the VPS, make sure Tailscale is running and that Traefik can access tailnet destinations:
   ```bash
   sudo tailscale up --accept-routes --ssh --advertise-tags=tag:traefik
   ```
3. Update your Tailscale ACLs to allow Traefik to reach the dashboard host. Example ACL snippet:
   ```json
   {
     "acls": [
       {"action": "accept", "src": ["tag:traefik"], "dst": ["100.101.102.103:8080"]}
     ],
     "tagOwners": {
       "tag:traefik": ["autogroup:admin"]
     }
   }
   ```
   Adjust IP and owners to match your environment.

### 5.2 Wire the service into Traefik
Create or update a dynamic configuration file consumed by Traefik (for example `/etc/traefik/dynamic/ticket-dashboard.yaml` or a mounted volume in the Traefik container):
```yaml
http:
  services:
    ticket-dashboard:
      loadBalancer:
        servers:
          - url: "http://100.101.102.103:8080"
        passHostHeader: true
  routers:
    ticket-dashboard:
      entryPoints:
        - websecure
      rule: "Host(`support.example.com`)"
      service: ticket-dashboard
      tls:
        certResolver: letsencrypt
  middlewares:
    ticket-dashboard-headers:
      headers:
        frameDeny: true
        contentTypeNosniff: true
```
Attach the middleware to the router by adding `middlewares: - ticket-dashboard-headers` if desired.

Reload Traefik (container restart or `docker kill -s HUP <traefik-container>` depending on your setup). Traefik now terminates TLS and proxies to the Tailscale IP.

### 5.3 DNS and verification
- Point `support.example.com` to the VPS public IP.
- Ensure the Traefik `websecure` entrypoint listens on TCP 443 and the `letsencrypt` resolver has permissions to request certificates.
- After DNS propagates, visit `https://support.example.com/health`; the response should match the internal health endpoint.

### 5.4 Optional fallback: reverse SSH tunnel
If Tailscale is unavailable, you can fall back to an SSH reverse tunnel that maps a remote VPS port to the local container and adjust the Traefik service to target `http://127.0.0.1:<remote-port>` instead.

## 6. Testing and monitoring
- Verify Portainer shows the container healthy and the Traefik dashboard reports the router/service as `UP`.
- Watch application logs with `docker logs ticket-dashboard` (locally) or through Portainer.
- Tailscale admin console should show both machines connected; enable key expiry notifications to avoid interruptions.

## 7. Troubleshooting tips
- If Traefik reports `BAD GATEWAY`, confirm the tailnet IP is reachable from the VPS: `curl http://100.101.102.103:8080/health` on the VPS.
- For ACL denials, check the Tailscale admin console logs.
- When using Google Sheets export, confirm `GOOGLE_SHEETS_CREDENTIALS_PATH` points to the mounted JSON file inside the container.
- For large datasets, allocate additional RAM/CPU to the Docker host to prevent Gunicorn workers from being OOM-killed.

With Tailscale providing the secure private link and Traefik handling TLS and routing, you can manage the app entirely from Portainer while serving the dashboard to the public internet through your VPS.
