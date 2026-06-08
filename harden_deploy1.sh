#!/bin/bash
# AYET nginx hardening — safe: backs up, tests before reload, never touches l1.
set -e

cp /etc/nginx/sites-available/ayet.aucfans.com /root/ayet-backups/nginx_ayet_$(date +%Y%m%d_%H%M%S).conf
cp /etc/nginx/nginx.conf /root/ayet-backups/nginx_conf_$(date +%Y%m%d_%H%M%S).conf
echo "configs backed up to /root/ayet-backups/"

# 1) enable server_tokens off (hide nginx version)
sed -i 's/# *server_tokens off;/server_tokens off;/' /etc/nginx/nginx.conf
echo "server_tokens: $(grep -n 'server_tokens' /etc/nginx/nginx.conf | head -1)"

# 2) add security headers + gate /swap/admin.html in the HTTPS server block
python3 - << 'PYEOF'
f="/etc/nginx/sites-available/ayet.aucfans.com"
s=open(f).read()
target='    location /support/ {'
block='''    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000" always;

    location = /swap/admin.html {
        auth_basic "AYET Admin";
        auth_basic_user_file /etc/nginx/.ayet_htpasswd;
        try_files $uri =404;
    }

    location /support/ {'''
if "X-Frame-Options" in s or "location = /swap/admin.html" in s:
    print("hardening already present; skipping insert")
elif target in s:
    s=s.replace(target, block, 1)
    open(f,"w").write(s)
    print("inserted security headers + /swap/admin.html gate")
else:
    print("ERROR: anchor 'location /support/' not found — NO change made")
PYEOF

# 3) test, then reload only if valid
nginx -t && nginx -s reload && echo "HARDENING_DONE" || echo "TEST FAILED — nothing reloaded; site unchanged. Restore: cp /root/ayet-backups/nginx_ayet_*.conf /etc/nginx/sites-available/ayet.aucfans.com"
