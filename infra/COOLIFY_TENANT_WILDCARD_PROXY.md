# Coolify Tenant Wildcard Proxy

Use this when the base production hosts already work:

- `https://menu.kepoli.com`
- `https://admin.menu.kepoli.com`

and only tenant subdomains still need routing:

- `https://<slug>.menu.kepoli.com`

This avoids putting the wildcard in the normal Coolify app domain field, which can fail with Traefik/ACME errors on this stack.

## Target topology

- Coolify app domains:
  - frontend: `https://menu.kepoli.com:3000`
  - admin: `https://admin.menu.kepoli.com:3000`
  - api: empty
- DNS:
  - `A menu -> VPS_IP`
  - `A admin.menu -> VPS_IP`
  - `A *.menu -> VPS_IP`
- Wildcard routing:
  - Traefik dynamic configuration on the Coolify server
  - custom wildcard certificate for `menu.kepoli.com` + `*.menu.kepoli.com`

## 1. DNS

At Hostinger, confirm:

- `menu` -> `85.31.239.111`
- `admin.menu` -> `85.31.239.111`
- `*.menu` -> `85.31.239.111`

Do not continue until `menu.kepoli.com` and `admin.menu.kepoli.com` already load successfully.

## 2. Keep the Coolify app domains exact-host only

In the Coolify resource:

- `Domains for frontend`: `https://menu.kepoli.com:3000`
- `Domains for admin`: `https://admin.menu.kepoli.com:3000`
- `Domains for api`: empty

Do not add `https://*.menu.kepoli.com:3000` there.

## 3. Generate a wildcard certificate on the VPS

Wildcard certificates require a DNS challenge. The provider-agnostic path is manual DNS with Certbot.

Install Certbot if needed:

```bash
sudo apt-get update
sudo apt-get install -y certbot
```

Request a certificate for the base host and wildcard:

```bash
sudo certbot certonly \
  --manual \
  --preferred-challenges dns \
  --agree-tos \
  -m admin@kepoli.com \
  -d menu.kepoli.com \
  -d '*.menu.kepoli.com'
```

Certbot will print one or more TXT records for `_acme-challenge.menu.kepoli.com`.

In Hostinger DNS:

1. add the TXT record(s) exactly as shown
2. wait for propagation
3. press Enter in the VPS terminal to continue issuance

After success, Certbot stores the files under:

- `/etc/letsencrypt/live/menu.kepoli.com/fullchain.pem`
- `/etc/letsencrypt/live/menu.kepoli.com/privkey.pem`

## 4. Copy the wildcard certificate into the Coolify proxy certificate path

Create the target directory:

```bash
sudo mkdir -p /data/coolify/proxy/certs/menu.kepoli.com
```

Copy the certificate files:

```bash
sudo cp /etc/letsencrypt/live/menu.kepoli.com/fullchain.pem /data/coolify/proxy/certs/menu.kepoli.com/fullchain.pem
sudo cp /etc/letsencrypt/live/menu.kepoli.com/privkey.pem /data/coolify/proxy/certs/menu.kepoli.com/privkey.pem
sudo chmod 600 /data/coolify/proxy/certs/menu.kepoli.com/privkey.pem
sudo chmod 644 /data/coolify/proxy/certs/menu.kepoli.com/fullchain.pem
```

## 5. Generate the Traefik wildcard router config from the live deployment

Manual YAML editing works, but it is fragile because the frontend target can change across redeploys.

Use the installer script on the VPS to render the correct target from the current running containers:

```bash
cd /opt/resto
bash infra/coolify/install_tenant_wildcard_proxy.sh \
  --resource-uuid <RESOURCE_UUID> \
  --base-domain menu.kepoli.com \
  --dry-run
```

Review the rendered YAML. Then install it:

```bash
cd /opt/resto
bash infra/coolify/install_tenant_wildcard_proxy.sh \
  --resource-uuid <RESOURCE_UUID> \
  --base-domain menu.kepoli.com
```

This writes a dynamic config file under:

- `/data/coolify/proxy/dynamic/kepoli-tenant-wildcard.yml`

The script:

- detects the current frontend container for the resource
- prefers the container hostname if the proxy can resolve it
- falls back to the shared-network IP when hostname resolution is not available
- emits the Traefik `ruleSyntax: v2` host-regexp format that is known to work on this stack

If you need to inspect the generated YAML without installing:

```bash
cd /opt/resto
bash infra/coolify/render_tenant_wildcard_proxy.sh \
  --resource-uuid <RESOURCE_UUID> \
  --base-domain menu.kepoli.com
```

## 6. Load the Traefik wildcard router into Coolify

Open:

- `Servers`
- your server
- `Proxy`
- `Dynamic Configurations`

Create a new dynamic configuration and paste the contents of the rendered file, or keep the file in the proxy dynamic directory if your Coolify proxy is already configured to load file-provider configs from there.

Reference template:

- [traefik-kepoli-tenant-wildcard.yml](C:/Users/user/resto/infra/coolify/traefik-kepoli-tenant-wildcard.yml)

The router does three things:

- redirects `http://<slug>.menu.kepoli.com` to HTTPS
- matches `https://<slug>.menu.kepoli.com`
- forwards that traffic to the working frontend service inside Docker

Important:

- the frontend service must expose the stable Traefik service label from [docker-compose.coolify.yml](C:/Users/user/resto/docker-compose.coolify.yml)
- the wildcard TLS files are referenced inside the proxy container as:
  - `/traefik/certs/menu.kepoli.com/fullchain.pem`
  - `/traefik/certs/menu.kepoli.com/privkey.pem`

## 7. Restart the Coolify proxy

After saving the dynamic configuration:

1. open `Servers`
2. click `Restart Proxy`

## 8. Verify the wildcard route

Test exact hosts first:

```bash
curl -I https://menu.kepoli.com/health
curl -I https://admin.menu.kepoli.com/health
curl -I https://menu.kepoli.com/api/health/
```

Then test wildcard routing with any sample slug:

```bash
curl -I https://smoke.menu.kepoli.com/health
```

Expected:

- `/health` returns `200`

If DNS has not propagated yet, force resolution from the VPS or a local machine:

```bash
curl -I --resolve smoke.menu.kepoli.com:443:85.31.239.111 https://smoke.menu.kepoli.com/health
```

After provisioning a real tenant (for example `demo.menu.kepoli.com`), verify tenant resolution through Django as well:

```bash
curl -I https://demo.menu.kepoli.com/health
curl -I https://demo.menu.kepoli.com/api/health/
```

Expected after provisioning:

- `/health` returns `200`
- `/api/health/` returns `200`

## 9. Why this works

- Coolify exact-host routing already handles:
  - `menu.kepoli.com`
  - `admin.menu.kepoli.com`
- the tenant wildcard is added at the proxy layer, not at the app-domain form layer
- Nginx preserves the original forwarded tenant host to Django, so host-based tenant resolution still works

## 10. Known limitation

The manual Certbot DNS path does not auto-renew by itself, and the rendered wildcard target should be regenerated after major resource recreation if Coolify changes the frontend container/network target.

Short-term:

- keep it for first production launch
- renew manually before expiry

Later:

- switch to automated DNS-challenge issuance through a supported DNS API workflow
- automate wildcard proxy regeneration after Coolify redeploy/resource recreate

## 11. Files involved

- [docker-compose.coolify.yml](C:/Users/user/resto/docker-compose.coolify.yml)
- [frontend/nginx.conf](C:/Users/user/resto/frontend/nginx.conf)
- [traefik-kepoli-tenant-wildcard.yml](C:/Users/user/resto/infra/coolify/traefik-kepoli-tenant-wildcard.yml)
- [render_tenant_wildcard_proxy.sh](C:/Users/user/resto/infra/coolify/render_tenant_wildcard_proxy.sh)
- [install_tenant_wildcard_proxy.sh](C:/Users/user/resto/infra/coolify/install_tenant_wildcard_proxy.sh)
- [DEPLOY_REAL_APP_COOLIFY.md](C:/Users/user/resto/DEPLOY_REAL_APP_COOLIFY.md)
