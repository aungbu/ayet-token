# 07 — Incident Library & Resolved Issues

*A growing record of problems encountered and how they were resolved. TrueAI references this to
recognize known issues ("we've seen this before"). Add new incidents over time.*

## Format for each entry
- Symptom → Cause → Fix → Prevention.

## Recorded incidents (AI/infra stack)
1. GPU stuck at high power/P2 at idle
   - Symptom: RTX 8000 at ~73W/P2 when idle.
   - Cause: persistence/clocks not reset after reboot.
   - Fix: `nvidia-smi -pm 1` + `-rgc` + `-rac` → drops to P8, ~11W.
   - Prevention: consider a boot systemd unit to set persistence mode.

2. Ollama models "not found" from Open WebUI
   - Cause: Ollama bind address + firewall blocking the Docker bridge.
   - Fix: OLLAMA_HOST=0.0.0.0:11434 (kept private by firewall) + ufw allow 172.17.0.0/16 +
     an After=docker.service drop-in so Ollama waits for the bridge on boot.

3. Reasoning models appear "stuck"
   - Cause: DeepSeek-R1 models generate a long thinking block before the answer; short curl
     timeouts cut them off.
   - Fix: allow more time; in the browser the thinking streams. Not a bug.

4. Slither upload fails to compile
   - Cause: contract pragma version differs from the default solc.
   - Fix: the audit app now auto-detects the pragma and selects that solc version; for
     imports not in node_modules, upload a flattened .sol.

5. WeasyPrint PDF render fails after a root-drive swap
   - Cause: system libraries (libpango, cairo, gdk-pixbuf, etc.) missing on the new root.
   - Fix: apt install the WeasyPrint system deps (cached at
     /mnt/ai/ai-stack-setup/WEASYPRINT_SYSTEM_DEPS.txt).

6. Root-drive swap — AI stack gone
   - Cause: booted an older clone predating the AI setup.
   - Fix: reinstall driver + Ollama + systemd services + nginx + WeasyPrint deps to the new
     root; data safe on the AI drive. IMPORTANT: never run the old drive again (same validator
     key = double-signing risk).

## Recorded incidents (L1)
- [FME to complete: real L1 incidents and their resolutions as they occur.]
