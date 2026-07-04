# 04 — Rollback & Disaster Recovery

*How to recover the FME L1 and AI stack from failures. TrueAI may explain these concepts but
escalates actual production recovery to the FME team. Items marked [FME to complete].*

## What is recoverable vs. not
- Chain data (/opt/FME/core/state): [FME to complete: backup frequency + location].
- Validator key: if lost, the validator identity is lost. [FME to complete: secure key backup].
- Genesis/config (/opt/FME/core/node1): should be version-controlled/backed up.
- AI stack: code + configs cached at /mnt/ai/ai-stack-setup/; models re-pullable; RAG
  rebuildable from the corpus.

## Backups (current state)
- AI/TrueAI backup: /mnt/ai/backups/truel1-ai-backup-YYYY-MM-DD.tar.gz (code, configs,
  Modelfiles, RAG index, reports — NOT the 350GB model weights, which are re-pullable).
- [FME to complete: L1 chain-data + key backup schedule, location, and restore procedure.]

## Node failure recovery (concepts — escalate execution)
- If fme-core stops: check `docker logs fme-core`, verify disk space and mounts, and involve
  the FME team before restarting (doc 08 rule 1).
- If the host root drive fails: the AI stack restores from /mnt/ai/ai-stack-setup/ (see the
  rebuild notes there). The L1 config/data live under /opt/FME on their own storage.
  [FME to complete: exact L1 restore steps.]

## Lessons already recorded (from real incidents — see doc 07)
- Never run two nodes with the same validator key (double-signing).
- After a root-drive swap, several system dependencies must be reinstalled (NVIDIA driver,
  Ollama, systemd services, nginx, WeasyPrint system libs) — the AI-stack cache documents these.

## Disaster recovery contacts
- [FME to complete: who to call, escalation order, and any provider/support contacts.]
