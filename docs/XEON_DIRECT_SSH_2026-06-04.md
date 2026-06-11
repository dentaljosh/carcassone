# Xeon direct-WSL-ssh — kill the cmd.exe hop (2026-06-04)

**Goal:** make `ssh xeon-wsl "a && b | c"` work like the laptop — no cmd.exe
mangling, no `wsl -d … -- bash -lc` wrapper, no stage_launcher chicken-egg.
Root cause of all Xeon friction: `ssh xeon` lands in **Windows cmd.exe**, which
eats every `&& | ; > ||` and inner quote before bash sees it.

## ✅ AS-EXECUTED (2026-06-05) — LIVE
`ssh xeon-wsl "echo OK && hostname && uname -r && whoami"` → `OK / VATECH-PC /
6.6.114.1-microsoft-standard-WSL2 / doctor`. **The cmd.exe hop is gone; operators
work.** What was done:
- **PART 1** ran (`scripts/xeon/xeon_wsl_sshd_setup.sh` via the share): sshd in
  WSL on **:2222**, key-only, 5800x pubkey added, `ssh.service` enabled+active.
- **PART 2 = portproxy (NOT mirrored)** — lower risk, no `wsl --shutdown`, no CIFS
  disruption: `netsh advfirewall … localport=2222` + `netsh interface portproxy
  add v4tov4 listenport=2222 connectaddress=<WSL_IP> connectport=2222`.
- **PART 3**: `Host xeon-wsl` added to 5800x `~/.ssh/config` (:2222, user doctor).
- **Fallback intact:** Windows sshd still on :22, so `ssh xeon` always works.
- **⚠️ Portproxy is pinned to the current WSL NAT IP** → after a Xeon WSL
  restart/reboot run **`scripts/xeon/refresh_xeon_wsl_proxy.sh`** (from the 5800x)
  to re-point it. Zero-maintenance alternative: switch to `networkingMode=mirrored`
  (one `wsl --shutdown`) — the mirrored runbook below is still the upgrade path.

---
### Original plan (mirrored variant — kept as the optional permanent upgrade)

## Recon (done 2026-06-04)
- WSL 2.7.3.0, kernel 6.6.114, **systemd running**, default user `doctor`.
- **openssh-server NOT installed** in WSL (no sshd/sshd_config).
- WSL IP `172.27.122.246` = **NAT** (`.wslconfig` has no `networkingMode`).
- **Passwordless sudo: YES** (WSL `doctor`).
- **`ssh xeon` is ELEVATED** (`net session` ok; `VATECH` is Administrator) →
  `netsh`/`schtasks`/`.wslconfig` edits all runnable over ssh, unattended.
- `.wslconfig`: `[wsl2]` memory=26GB processors=12 swap=8GB (last section → safe
  to append `networkingMode=mirrored`).

## Execute AFTER the validation loop fully exits (Xeon free; avoids gate race)

**PART 1 — WSL-side (install sshd:2222, key-only).** Ready on the share:
```bash
ssh xeon "wsl -d Ubuntu-24.04 -- bash /mnt/carc-shared/code_sync/xeon_wsl_sshd_setup.sh"
```
(installs openssh-server, Port 2222, key-only, adds the 5800x pubkey, enables
+ starts ssh; idempotent. needs WSL internet for apt — Xeon LAN has it.)

**PART 2 — Windows-side (elevated; each is an operator-free single command).**
```bash
# firewall: allow inbound 2222
ssh xeon "netsh advfirewall firewall add rule name=WSL-ssh-2222 dir=in action=allow protocol=TCP localport=2222"
# mirrored networking → WSL shares the LAN IP 192.168.0.110 (so :2222 is reachable)
ssh xeon "findstr /C:networkingMode %USERPROFILE%\.wslconfig || echo networkingMode=mirrored >> %USERPROFILE%\.wslconfig"
# apply: shutdown (kills WSL — safe once validation is done) then restart to re-read .wslconfig
ssh xeon "wsl --shutdown"
ssh xeon "wsl -d Ubuntu-24.04 -- echo wsl-restarted"   # re-runs sshd via systemd-enabled ssh.service
```

**PART 3 — local ~/.ssh/config (5800x AND Mac):**
```
Host xeon-wsl
  HostName 192.168.0.110
  Port 2222
  User doctor
  IdentityFile ~/.ssh/id_ed25519
```

**VERIFY:**
```bash
ssh xeon-wsl "echo ok && hostname && nvidia-smi.exe --query-gpu=name --format=csv,noheader | head -1"
# operators work directly → cmd.exe hop is gone.
```

## PART 4 (optional, fiddlier) — keep WSL alive at boot
Fixes the "WSL2 VM teardown kills nohup'd jobs" rule so plain `nohup` survives
(no more held-ssh foreground). SYSTEM-launched `wsl.exe` is uncertain — do +
verify separately; the held-ssh pattern remains the fallback if it doesn't take.

### ✅ PROVEN held-ssh keepalive (2026-06-11) — `scripts/xeon/xeon_keepalive_loop.sh`
The idle-VM-teardown was the root cause of the 2026-06-11 `:2222` "flap"
(intermittent banner-timeout / reset-by-peer on :2222 while Windows :22 stayed
up; the WSL sshd itself was clean — 3/3 on localhost-inside-WSL). The portproxy
config and WSL IP were both correct/stable — the VM was simply being torn down
when idle, dropping the NAT proxy **and** the CIFS mount together. Fix: `nohup`
this loop on the 5800x ONCE — it holds the VM via the reliable legacy port-22
`sleep infinity` and self-heals (re-refresh proxy + re-mount share) on any drop.
Took `ssh xeon-wsl` from 0/6 → 6/6 over a 30s window. This is the recommended
keepalive (supersedes the manual one-shot); the **mirrored-mode upgrade above is
the permanent alternative** that removes the need for it entirely (but needs one
`wsl --shutdown`, so do it only when xeon is FREE).
```bash
ssh xeon "schtasks /create /tn KeepWSLAlive /tr \"wsl.exe -d Ubuntu-24.04 -u root /bin/sleep infinity\" /sc onstart /ru SYSTEM /rl highest /f"
```

## Payoff / cleanup once verified
- Cluster loop `run_pathb_cluster_loop.sh` xeon branch can drop the
  `wsl -d … -- bash -lc` gymnastics → use the laptop path (`ssh xeon-wsl …`).
- Retires/relaxes: `feedback_xeon_ssh_quoting`, the stage_launcher chicken-egg,
  and (with PART 4) the WSL2-teardown held-ssh rule.
- **Fallback preserved throughout:** Windows sshd stays on :22, so `ssh xeon`
  (cmd.exe path) always works if anything goes wrong → no lock-out risk.
