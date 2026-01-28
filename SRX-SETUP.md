# Juniper SRX340 – J-Flow (NetFlow v9) Export for FastNetMon

This document describes a **known-working configuration** for exporting **J-Flow (NetFlow v9)** from a **Juniper SRX340** to a **FastNetMon Community** server.

The purpose of this setup is **traffic visibility and DDoS detection**.  
Mitigation (RTBH or source blocking) is handled separately.

---

## Environment

- Device: Juniper SRX340
- Junos OS: 20.4R3.x
- WAN type: PPPoE
- Routed interface: `pp0.0`
- Flow protocol: NetFlow v9 (J-Flow / inline-jflow)
- Flow collector: FastNetMon Community
- Export protocol: UDP
- Export port: 2055

---

## Important Notes

- SRX340 **does not support sFlow**
- J-Flow exports traffic **pre-NAT**
- NetFlow/J-Flow **does not block traffic**
- On Junos 20.4+, sampling **must be configured using an instance**
- Sampling **cannot** be applied to `ppp-over-ether` units
- Sampling **must** be applied to the routed interface (`pp0.0`)

---

## Step 1 – Create a NetFlow v9 Template

```junos
set services flow-monitoring version9 template IPV4-JFLOW-TEMPLATE ipv4-template
set services flow-monitoring version9 template IPV4-JFLOW-TEMPLATE flow-active-timeout 60
set services flow-monitoring version9 template IPV4-JFLOW-TEMPLATE flow-inactive-timeout 15
set services flow-monitoring version9 template IPV4-JFLOW-TEMPLATE template-refresh-rate packets 1000
set services flow-monitoring version9 template IPV4-JFLOW-TEMPLATE option-refresh-rate packets 1000
```

---

## Step 2 – Create a Sampling Instance

```junos
set forwarding-options sampling instance FNM input rate 1000
set forwarding-options sampling instance FNM input max-packets-per-second 5000
set forwarding-options sampling instance FNM input run-length 0
```

---

## Step 3 – Configure NetFlow Export to FastNetMon

```junos
set forwarding-options sampling instance FNM family inet output flow-server <FASTNETMON_IP> port 2055
set forwarding-options sampling instance FNM family inet output flow-server <FASTNETMON_IP> version9 template IPV4-JFLOW-TEMPLATE
```

---

## Step 4 – Configure inline-jflow Source Address

```junos
set forwarding-options sampling instance FNM family inet output inline-jflow source-address <SRX_EXPORT_SOURCE_IP>
```

---

## Step 5 – Enable Sampling on the Routed Interface

```junos
set interfaces pp0 unit 0 family inet sampling input
```

---

## Step 6 – Commit Configuration

```junos
commit
```

---

## Step 7 – Verify on the SRX

```junos
show configuration forwarding-options sampling | display set
show configuration services flow-monitoring | display set
show interfaces pp0 terse
```

---

## Step 8 – Verify on the FastNetMon Server

```bash
sudo tcpdump -ni any udp port 2055
```

```bash
tail -f /var/log/fastnetmon.log
```

---

## Known Limitations

- NetFlow is exported **pre-NAT**
- Public destination IPs may not appear in flows
- FastNetMon Community focuses on **victim-based mitigation (RTBH)**

---

## Summary

✔ J-Flow export is active  
✔ FastNetMon receives NetFlow v9  
✔ Sampling is applied correctly  

