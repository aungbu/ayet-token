#!/bin/bash
# Restrict SSH to home IP + office LAN. Port 22 ONLY — does not touch 80/443 or node ports.
# Arms a 10-minute auto-revert so you cannot lock yourself out.
HOME_IP="66.215.199.71"
OFFICE_LAN="192.168.1.0/24"

# 1) snapshot current firewall (used by auto-revert and manual restore)
iptables-save > /root/iptables.before.rules
echo "current rules saved -> /root/iptables.before.rules"

# 2) arm auto-revert in 10 min (survives disconnect). Reopens SSH unless you persist.
systemctl stop ssh-revert.timer 2>/dev/null
systemctl reset-failed ssh-revert.service 2>/dev/null
if systemd-run --on-active=10min --unit=ssh-revert bash -c 'iptables-restore < /root/iptables.before.rules' 2>/dev/null; then
  echo "AUTO-REVERT armed: limits undo themselves in 10 min unless you run the persist step."
else
  echo "WARNING: auto-revert could not be armed. KEEP THIS SESSION OPEN while you test."
fi

# 3) apply port-22-only allowlist (order: home accept, office accept, then drop the rest)
iptables -I INPUT 1 -p tcp --dport 22 -j DROP
iptables -I INPUT 1 -p tcp --dport 22 -s "$OFFICE_LAN" -j ACCEPT
iptables -I INPUT 1 -p tcp --dport 22 -s "$HOME_IP" -j ACCEPT

echo
echo "SSH (port 22) now allowed ONLY from:"
echo "  - $HOME_IP   (home)"
echo "  - $OFFICE_LAN (office LAN)"
echo "Active port-22 rules:"
iptables -S INPUT | grep -- '--dport 22'
echo "SSH_LOCK_APPLIED"
