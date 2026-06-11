#!/bin/bash
HT=/etc/nginx/.wst_htpasswd
CONF=/etc/nginx/sites-available/wst.aucfans.com

if [ ! -f "$HT" ]; then
  echo "ABORT: $HT does not exist yet."
  echo "Run this first (you'll type the password):"
  echo "    htpasswd -c $HT admin"
  exit 1
fi

mkdir -p /root/ayet-backups
cp "$CONF" /tmp/wst_conf.bak
cp "$CONF" "/root/ayet-backups/wst_nginx_$(date +%Y%m%d_%H%M%S).conf.bak"
echo "backed up current config"

cat > "$CONF" <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name wst.aucfans.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name wst.aucfans.com;

    root /var/www/wst.aucfans.com;
    index index.html;

    server_tokens off;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    auth_basic "WST - restricted";
    auth_basic_user_file /etc/nginx/.wst_htpasswd;

    ssl_certificate /etc/letsencrypt/live/wst.aucfans.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wst.aucfans.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / { try_files $uri $uri/ =404; }
}
NGINX

if nginx -t 2>/tmp/ngx.err; then
    nginx -s reload 2>/dev/null || systemctl reload nginx
    echo "WST_AUTH_DONE -- https://wst.aucfans.com now asks for login (user: admin)"
else
    echo "NGINX TEST FAILED -- restoring previous config, nothing changed:"
    cat /tmp/ngx.err
    cp /tmp/wst_conf.bak "$CONF"
    nginx -s reload 2>/dev/null || systemctl reload nginx
fi
