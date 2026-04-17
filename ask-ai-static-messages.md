# Ask AI — Static Welcome Messages

> Collected from engineers via [CXP-27414](https://cisco-cxe.atlassian.net/browse/CXP-27414).  
> Last updated: 2026-04-17

---

## 1. Collected Responses

### 1.1 LDOS Agent
> Source: [CXP-27416](https://cisco-cxe.atlassian.net/browse/CXP-27416) — Colin Alberts

---

I can help you explore your Cisco install base. Here are my capabilities:

- **Lifecycle & LDOS** — find assets past or approaching end-of-life milestones
- **Coverage & contracts** — check contract status, warranty, and renewal windows
- **Security advisories** — surface PSIRTs and vulnerabilities by severity
- **Inventory breakdowns** — filter by product family, location, software type, tags, and more
- **Telemetry & connectivity** — see which devices are connected and last signal dates

What would you like to know?

---

### 1.2 Config Best Practices (CBP) Agent
> Source: [CXP-27415](https://cisco-cxe.atlassian.net/browse/CXP-27415) — Abhishek Siripurapu

---

Hello! I can help you analyze and understand network configuration assessment results. Below is a quick overview of what I'm able to assist with.

#### Assessment Summary & Overview
- Retrieve the latest assessment summary, including total findings, severity distribution, most impacted assets, and the rules most frequently identified as Did Not Pass.

#### Asset-Scope Analysis
- Analyze findings for specific assets by filtering on attributes such as hostname, IP address, product family, location, software type or version, and other asset properties.

#### Rule Analysis
- Explore configuration rules by ID or name, including their severity, impact, affected assets, and how frequently they are marked as Did Not Pass.

#### Signature Asset Insights
- Access pre-generated AI insights that highlight key patterns, risks, and recommendations for Signature assets from the latest assessment.

If you'd like, ask a question or choose an area to explore and I'll help you analyze the data.

---

### 1.3 Security Hardening Agent
> Source: [CXP-27417](https://cisco-cxe.atlassian.net/browse/CXP-27417) — Ronnit Burman

---

I can help you with:

- Baseline hardening guidance for Cisco platforms
- Exposure summaries for failed hardening checks

Try asking:

- What are Cisco security hardening best practices for network devices?
- How do I harden my Cisco IOS XE devices?
- How many assets are in violation of security hardening best practices?

---

### 1.4 Security Advisory Agent
> Source: [CXP-27417](https://cisco-cxe.atlassian.net/browse/CXP-27417) — Ronnit Burman

---

I can help you with:

- Advisory lookup by topic, protocol, or vulnerability
- Impact analysis across devices and advisories
- Risk-oriented summaries for current exposure

Try asking:

- Are there any advisories related to DHCP?
- Before I enable HTTP, are there known PSIRT advisories related to enabling HTTP?
- How many devices are vulnerable to security advisories?

---

### 1.5 Assessment Rating Agent (formerly HRI)
> Source: [CXP-27418](https://cisco-cxe.atlassian.net/browse/CXP-27418) — Mohammad Hanan Bhat  
> Note: Comment posted on parent epic CXP-27414.  
> Note: Engineer posted a **detailed mid-conversation response**, not a welcome/opening message. No welcome message has been submitted yet. The "What I Can Help You With" section extracted below provides the capability reference.

**Capabilities (from a live response):**

- Detailed breakdown of which assessment type contributes most to the rating
- Prioritizing findings that most impact the rating category
- Identifying which issues are keeping the device in the Critical category
- Showing how the rating would change if specific findings were resolved
- Comparing this device's rating with other high or critical assets in the environment
- Identifying similar devices affected by the same findings

---

## 2. Style Analysis

Across all four agents, the following patterns are consistent:

| Property | Pattern |
|---|---|
| **Greeting** | Present in CBP ("Hello!"). Absent or implied in LDOS and SH/SA. |
| **Capability structure** | All use a bullet list. CBP uses H3 sections per capability area. SH/SA uses flat bullets under a "I can help you with:" lead-in. LDOS uses bold labels with an em-dash and inline description. |
| **Capability label style** | Bold short noun phrase (CBP uses H3 header, LDOS uses `**Label** —`, SH/SA uses plain text) |
| **Example questions** | Present only in SH/SA ("Try asking:"). Absent in LDOS and CBP. |
| **Closing invitation** | Always present. Either a question ("What would you like to know?") or an open prompt ("ask a question or choose an area"). |
| **Tone** | Direct, action-oriented, no marketing language. First person. |
| **Length** | Short. Capabilities are one-liners, not full paragraphs. |

**Most complete pattern** (combines greeting + structured capabilities + invitation): CBP agent.  
**Most scannable pattern** (bold labels + one-liner descriptions): LDOS agent.  
**Most interactive pattern** (example prompts lower the barrier to entry): SH/SA agents.

---

## 3. Proposed Welcome Message — Assessment Rating Agent

> Synthesizes the CBP structure with the LDOS label style and the SH/SA example-question approach, applied to the Assessment Rating agent's capabilities.

---

Hello! I can help you understand and act on your asset assessment ratings across Cisco IQ. Here is what I can do.

#### Fleet Assessment Overview
- Retrieve a summary of assessment ratings across your entire install base, filtered by severity (Critical, High, Medium, Low) or asset count.

#### Asset Rating Detail
- Analyze the assessment rating for a specific device and explain which findings drive it into its current risk category.

#### Cross-Assessment Breakdown
- Break down how each assessment domain — Security Advisories, Configuration Best Practices, Security Hardening, and Field Notices — contributes to an asset's overall rating.

#### Remediation Prioritization
- Identify which findings have the highest impact on the rating and prioritize remediation to move an asset out of the Critical or High category.

#### Comparative Analysis
- Compare rating distributions across your environment and surface assets that share the same high-impact findings.

If you'd like, ask a question or choose an area to explore and I'll help you analyze the data.

---
