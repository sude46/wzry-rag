# Deployment

Current server layout:

```text
browser
  -> http://<server-ip>:80
  -> nginx
  -> 127.0.0.1:8000 (wzry-rag Docker app)
  -> redis container (internal compose network)
```

The app container is intentionally bound to `127.0.0.1:8000`, so port 8000 is
not directly exposed. Nginx is the only public entrypoint.

## Apply

```bash
sudo apt update
sudo apt install -y nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/wzry-rag
sudo ln -sf /etc/nginx/sites-available/wzry-rag /etc/nginx/sites-enabled/wzry-rag
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Open TCP 80 in the cloud security group, then:

```text
http://<server-ip>/web/
```

`docker-compose.yml` keeps the app local:

```yaml
ports:
  - "127.0.0.1:8000:8000"
```

## Adding the creator project later

### Option A: subdomain (recommended)

DNS:

```text
creator.example.com -> <server-ip>
```

Nginx:

```nginx
server {
    listen 80;
    server_name creator.example.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

Docker:

```yaml
ports:
  - "127.0.0.1:8001:8000"
```

This does not collide with the current site: Nginx routes by the HTTP Host
header. The `wzry-rag` server block remains the default for bare-IP requests.

### Option B: path prefix `/creator/`

Nginx:

```nginx
location /creator/ {
    proxy_pass http://127.0.0.1:8001/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

This only works cleanly if the creator app supports a base path
(`/creator/`). SPAs with absolute asset/API paths will break; use a subdomain
or a separate port instead.

### Option C: separate port

Expose `127.0.0.1:8001` as a public port in the security group and access
`http://<server-ip>:8001/`. No Nginx change needed, but the URL keeps the port.

## HTTPS

A trusted HTTPS certificate normally requires a domain. Point the domain at the
server, add an Nginx `server_name`, then use Certbot or another ACME client.
For bare-IP HTTP only, the current port-80 setup is enough.
