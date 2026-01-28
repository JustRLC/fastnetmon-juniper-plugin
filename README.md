# FastNetMon → Juniper SRX NETCONF Blackhole Integration

This repository provides a **FastNetMon Community Edition integration** that uses **NETCONF** to automatically **blackhole attacking IPs on a Juniper SRX firewall** by installing and removing `/32 discard static routes`.

## FYI 

This has only been tested on:

-  Debian 12 OS
- Juniper SRX340

It supports:

- Automatic bans from FastNetMon
- Optional **commit confirmed** (auto-expiring bans – recommended)
- Explicit unban support
- Email notifications (Not fully tested)
- NETCONF over SSH (no CLI scraping)

---

## Architecture Overview

```
Traffic → FastNetMon Flow server → notify_attack.sh → Python NETCONF → Juniper SRX
```

1. FastNetMon detects an attack  
2. `notify_attack.sh` is triggered  
3. Python script uses NETCONF to:
   - **BAN**: add `/32 discard` route
   - **UNBAN**: remove the route  
4. Optional `commit confirmed` ensures no stuck blackholes

---

## 🚀 FastNetMon Community Server Setup

If you don’t already have FastNetMon running:

**Official documentation:**  
👉 https://fastnetmon.com/install/

### Quick install (Ubuntu / Debian)

```bash
wget https://install.fastnetmon.com/installer -Oinstaller
sudo chmod +x installer
sudo ./installer -install_community_edition
```

Verify service status:

```bash
systemctl status fastnetmon
```

---

## 📦 Installing the Juniper SRX Integration

### 1️⃣ Install the scripts

```bash
# Python NETCONF script
cp srx_netconf_blackhole.py /usr/local/bin/
chmod +x /usr/local/bin/srx_netconf_blackhole.py

# FastNetMon notify script
cp notify_attack.sh /usr/local/bin/
chmod +x /usr/local/bin/notify_attack.sh
```

---

### 2️⃣ Configure FastNetMon to use the notify script

Edit the FastNetMon configuration:

```bash
nano /etc/fastnetmon.conf
```

Ensure this line exists:

```conf
notify_script_path: /usr/local/bin/notify_attack.sh
```

Restart FastNetMon:

```bash
systemctl restart fastnetmon
```

---

## 🧠 How the Integration Works

### Ban Action

- Triggered when FastNetMon detects an attack
- Adds a `/32 discard` static route on the SRX
- Uses NETCONF with candidate configuration and commit

### Unban Action

- Triggered when FastNetMon clears the attack
- Removes the static route
- **Always uses a normal commit** (never commit confirmed)

---

## ⚙️ Python Script Parameters

### Required

| Parameter       | Description               |
| --------------- | ------------------------- |
| `ban` / `unban` | Action to perform         |
| `--host`        | SRX management IP         |
| `--user`        | NETCONF username          |
| `--ip`          | IPv4 address to ban/unban |

### Authentication

| Parameter    | Description                               |
| ------------ | ----------------------------------------- |
| `--ssh-key`  | Path to SSH private key (**recommended**) |
| `--password` | Password authentication (not recommended) |

### NETCONF / Safety

| Parameter               | Default | Description                        |
| ----------------------- | ------- | ---------------------------------- |
| `--timeout`             | 120     | NETCONF RPC timeout (seconds)      |
| `--commit-confirmed`    | ON      | Enable commit confirmed (BAN only) |
| `--no-commit-confirmed` | OFF     | Disable commit confirmed           |
| `--confirm-timeout`     | 600     | Auto-rollback time (seconds)       |
| `--hostkey-verify`      | OFF     | Enable SSH host key verification   |

> ⚠️ **Important:**  
> `commit confirmed` is **automatically disabled for unban**, even if enabled globally, to prevent rollback loops.

---

## 🧩 notify_attack.sh Configuration Variables

At the top of `notify_attack.sh`:

```bash
EMAIL_NOTIFY="me@example.com"

SRX_HOST="" # 192.168.0.1
SRX_USER="" # 
SRX_KEY="" # /root/.ssh/id_rsa

USE_COMMIT_CONFIRMED=true
CONFIRM_TIMEOUT=600
```

### Commit Confirmed Toggle

| Value   | Behavior                            |
| ------- | ----------------------------------- |
| `true`  | Auto-expiring bans  (recommended)   |
| `false` | Permanent bans until explicit unban |

---

## 🔐 Juniper SRX NETCONF Configuration

### 1️⃣ Enable NETCONF over SSH

```junos
set system services netconf ssh
```

---

### 2️⃣ Create a NETCONF User

```junos
set system login user fastnetmon class super-user
set system login user fastnetmon authentication ssh-rsa "ssh-rsa AAAA..."
commit
```

> 🔒 You may later replace `super-user` with a restricted class if desired.

---

### 3️⃣ Verify NETCONF Access

From the FastNetMon server:

```bash
ssh -p 830 fastnetmon@SRX_MGMT_IP -s netconf
```

You should see NETCONF XML capabilities returned.

---

## 🧪 Testing

### Manual Test (Recommended)

```bash
python3 /usr/local/bin/srx_netconf_blackhole.py ban \
  --host {SRX_MGMT_IP} --user fastnetmon --ssh-key {SSH KEY} \
  --ip {ATTACKER IP}
```

Verify on SRX:

```junos
show configuration routing-options static | display set | match {ATTACKER IP}
```

---

### FastNetMon Trigger Test (Lab Only)

```bash
hping3 -S --flood -p 443 <target_ip>
```

Monitor logs:

```bash
journalctl -u fastnetmon -f
journalctl -t fastnetmon-notify -f
tail -f /var/log/fastnetmon-srx-netconf.log
```

---

## 🔮 Future Enhancements

- BGP RTBH (upstream blackholing)
- Batch multiple IPs per commit
- IPv6 support
- Routing-instance isolation
- Rate-limit commits for large attacks

---

## 🙌 Credits

- FastNetMon Community Edition  - https://github.com/pavel-odintsov

---

## 💬 Support & Disclaimer

This is community-driven automation. 
Always test in a lab environment before deploying to production.