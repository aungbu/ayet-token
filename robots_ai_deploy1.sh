#!/bin/bash
# Block AI crawlers (training + AI-answer) while keeping Google/Bing.
# Two layers: robots.txt (opt-out) + nginx 403 (enforced). Touches ONLY the ayet site. Tests before reload.
set -e
WEBROOT=/var/www/ayet.aucfans.com
CONF=/etc/nginx/sites-available/ayet.aucfans.com

# 1) robots.txt
cat > "$WEBROOT/robots.txt" << 'ROBOTS'
# AYET — crawler policy
# Search engines: ALLOWED (so customers can find us). AI scrapers: BLOCKED.

User-agent: Googlebot
Allow: /

User-agent: Bingbot
Allow: /

# --- AI crawlers: blocked (training + AI-answer/retrieval) ---
User-agent: GPTBot
Disallow: /
User-agent: OAI-SearchBot
Disallow: /
User-agent: ChatGPT-User
Disallow: /
User-agent: ClaudeBot
Disallow: /
User-agent: anthropic-ai
Disallow: /
User-agent: Claude-Web
Disallow: /
User-agent: Claude-SearchBot
Disallow: /
User-agent: Claude-User
Disallow: /
User-agent: PerplexityBot
Disallow: /
User-agent: Perplexity-User
Disallow: /
User-agent: CCBot
Disallow: /
User-agent: Google-Extended
Disallow: /
User-agent: Applebot-Extended
Disallow: /
User-agent: Amazonbot
Disallow: /
User-agent: Bytespider
Disallow: /
User-agent: FacebookBot
Disallow: /
User-agent: meta-externalagent
Disallow: /
User-agent: Meta-ExternalFetcher
Disallow: /
User-agent: cohere-ai
Disallow: /
User-agent: Diffbot
Disallow: /
User-agent: Omgilibot
Disallow: /
User-agent: ImagesiftBot
Disallow: /
User-agent: YouBot
Disallow: /
User-agent: Timpibot
Disallow: /

# Everyone else (other search engines, etc.): allowed
User-agent: *
Allow: /
ROBOTS
echo "robots.txt written ($(wc -l < "$WEBROOT/robots.txt") lines)"

# 2) backup nginx config
cp "$CONF" /root/ayet-backups/nginx_ayet_$(date +%Y%m%d_%H%M%S).conf
echo "nginx config backed up"

# 3) add UA map + 403 rule (idempotent). Map is http-context (top of file); 403 only in the ayet 443 block — l1 untouched.
python3 - << 'PYEOF'
conf="/etc/nginx/sites-available/ayet.aucfans.com"
s=open(conf).read()
if "$ai_bot" in s:
    print("AI-bot rule already present; skipping")
else:
    mapblock='''map $http_user_agent $ai_bot {
    default 0;
    "~*GPTBot" 1;
    "~*OAI-SearchBot" 1;
    "~*ChatGPT-User" 1;
    "~*ClaudeBot" 1;
    "~*anthropic-ai" 1;
    "~*Claude-Web" 1;
    "~*Claude-SearchBot" 1;
    "~*Claude-User" 1;
    "~*PerplexityBot" 1;
    "~*Perplexity-User" 1;
    "~*CCBot" 1;
    "~*Amazonbot" 1;
    "~*Bytespider" 1;
    "~*FacebookBot" 1;
    "~*meta-externalagent" 1;
    "~*Meta-ExternalFetcher" 1;
    "~*cohere-ai" 1;
    "~*Diffbot" 1;
    "~*Omgilibot" 1;
    "~*ImagesiftBot" 1;
    "~*YouBot" 1;
    "~*Timpibot" 1;
}

'''
    anchor='    add_header X-Frame-Options "SAMEORIGIN" always;'
    if anchor in s:
        s = mapblock + s
        s = s.replace(anchor, '    if ($ai_bot) { return 403; }\n'+anchor, 1)
        open(conf,"w").write(s)
        print("inserted AI-bot map + 403 rule into ayet HTTPS block")
    else:
        print("ERROR: header anchor not found — NO change made")
PYEOF

# 4) test, reload only if valid
nginx -t && nginx -s reload && echo "AI_BLOCK_DONE" || echo "TEST FAILED — nothing reloaded; restore: cp /root/ayet-backups/nginx_ayet_*.conf $CONF"
