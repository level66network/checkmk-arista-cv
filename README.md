# Arista CloudVision (CVP / CVaaS) — checkmk Plugin

Monitor devices managed by **Arista CloudVision**, either a self-hosted **CloudVision Portal (CVP)** instance or **CloudVision as a Service (CVaaS)**, directly from checkmk. The plugin uses the [cvprac](https://github.com/aristanetworks/cvprac) REST API client to query CloudVision and surfaces per-device health as native checkmk services.

## Requirements

| Component | Minimum version |
|-----------|----------------|
| checkmk | 2.5.0p6 |
| Python | 3.8+ (on the checkmk server) |
| Arista CVP (on-prem) | Any supported version |
| Arista CVaaS | Token auth requires CVP 2020.3.0+ |

> **cvprac** (Arista's REST client library) is bundled inside the MKP and requires no separate installation.

## What it monitors

One **Arista CVP Info** service on the CVP/CVaaS host:
- Software version

One **Arista CVP Device \<hostname\>** service per managed device (on the CVP host):

| Metric | Default state |
|--------|--------------|
| Connection status (Connected / Registered / Disconnected) | Disconnected → CRIT |
| Compliance (OK / WARNING / ERROR) | WARNING → WARN, ERROR → CRIT |
| Streaming telemetry (Active / Inactive) | Inactive → WARN |

All thresholds are configurable via **Setup → Services → Service monitoring rules → Arista CVP Device Status**.

## Piggyback mode

Enable **piggyback mode** in the agent rule to additionally place an **Arista CVP Status** service on each device's own checkmk host. The piggyback host name can be matched by CVP hostname, FQDN, or IP address.

## Authentication

The rule offers two deployment types, each with their own authentication options:

### CloudVision Portal (CVP)

- **Username / Password** — CVP local or LDAP account.
- **Service Account Token** — available from CVP 2020.3.0 and later; recommended for automation. Generate tokens under **Settings → Access Control → Service Accounts** in the CVP UI.

### CloudVision as a Service (CVaaS)

CVaaS requires a **service account token**. Username/password auth is not supported. Generate tokens the same way: **Settings → Access Control → Service Accounts**.

Known regional endpoints:

| Region | Endpoint |
|--------|----------|
| US 1a | `www.arista.io` |
| US 1c | `www.cv-prod-us-central1-c.arista.io` |
| Canada | `www.cv-prod-na-northeast1-b.arista.io` |
| Europe West 2 | `www.cv-prod-euwest-2.arista.io` |
| Japan | `www.cv-prod-apnortheast-1.arista.io` |
| Australia | `www.cv-prod-ausoutheast-1.arista.io` |

> **Note:** URLs without `www` are not supported by cvprac.

For CVaaS, create a dedicated checkmk host (e.g. `cvp-cvaas`) and set its IP address/hostname to the regional endpoint. The agent rule overrides the host address with the endpoint configured in the rule form, so the host exists purely as a rule anchor.

## Setup

### 1. Install the MKP

```
mkp install arista_cv-$version.mkp
cmk -R
```

The MKP is available on the [GitHub releases page](https://github.com/level66network/checkmk-arista-cv/releases).

### 2. Create a checkmk host for CloudVision

Add a host in checkmk that represents your CVP instance or CVaaS tenant:

- **CVP (on-prem):** set the host IP/address to your CVP server's hostname or IP.
- **CVaaS:** set the host address to the regional endpoint (e.g. `www.arista.io`). The special agent overrides the address at runtime, so the host just serves as a rule anchor.

### 3. Configure the agent rule

Go to **Setup → Agents → Other integrations → Networking** and add the rule **Arista CloudVision (CVP / CVaaS)** to the host you created above.

Fill in the required fields:

| Field | CVP | CVaaS |
|-------|-----|-------|
| Deployment type | CloudVision Portal (CVP) | CloudVision as a Service (CVaaS) |
| Authentication | Username/Password **or** Service Account Token | Service Account Token (required) |
| Endpoint | _(taken from host address)_ | Regional hostname (e.g. `www.arista.io`) |
| HTTPS port | 443 (default) | — |

Optionally enable **piggyback mode** to push an **Arista CVP Status** service onto each device's own checkmk host. If you do, set **Piggyback host identifier** to match the field (hostname / FQDN / IP) that checkmk uses as the host name for those devices.

### 4. Discover services

Run a **service discovery** on the CloudVision host. You should see:

- One **Arista CVP Info** service (software version)
- One **Arista CVP Device \<hostname\>** service per managed device

## Building from source

```
python3 build_mkp.py        # produces arista_cv-<version>.mkp
```

or simply:

```
make build
```

## Author

[level66.network UG (haftungsbeschränkt)](https://level66.network)
