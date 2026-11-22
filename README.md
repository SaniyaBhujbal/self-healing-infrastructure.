# Self-Healing Infrastructure with Prometheus, Alertmanager & Ansible

> **Implementation status:** The local NGINX + systemd self-healing prototype has been tested. The Prometheus/Alertmanager integration in this repository is a deployment-ready lab scaffold and must still be deployed and validated on the target Ubuntu VM before it is described as completed.

## Objective
Monitor an Ubuntu-hosted NGINX service with Prometheus. When a Blackbox Exporter probe detects that HTTP is unavailable, Prometheus fires an alert, Alertmanager sends a webhook, and a small webhook receiver invokes an Ansible playbook to restart NGINX.

## Architecture
`NGINX on Ubuntu :80` → `Blackbox Exporter` → `Prometheus + alert rules` → `Alertmanager webhook` → `Flask webhook receiver on Ubuntu` → `Ansible playbook` → `systemctl restart nginx`

## Prerequisites
- Ubuntu VM with NGINX installed and listening on port 80.
- Docker Engine and Docker Compose plugin.
- Python 3, pip/venv, Ansible.
- Run this lab on a trusted local VM only. The webhook receiver is intentionally unauthenticated for a local demo; do not expose it to the internet.

## 1. Configure and start the monitoring stack
```bash
cd monitoring
docker compose up -d
docker compose ps
```
Prometheus: http://localhost:9090  
Alertmanager: http://localhost:9093  
Blackbox Exporter: http://localhost:9115

The compose file maps the host gateway as `host.docker.internal`, allowing Blackbox Exporter to probe NGINX on the Ubuntu host.

## 2. Start the webhook receiver
From the repository root:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r webhook/requirements.txt
sudo -E .venv/bin/python webhook/app.py
```
Keep this terminal open for the demo. The receiver listens on port 5001 and runs the fixed playbook in `ansible/restart-nginx.yml` only for the `NginxDown` alert. It does not accept arbitrary commands from webhook payloads.

## 3. Validate the alert-to-recovery chain
In a second terminal, watch logs:
```bash
docker compose -f monitoring/docker-compose.yml logs -f alertmanager prometheus blackbox
```
Trigger a failure:
```bash
sudo systemctl stop nginx
```
The alert rule requires the probe to fail for 20 seconds. Allow time for Prometheus evaluation and Alertmanager delivery. Then inspect:
```bash
systemctl is-active nginx
sudo journalctl -u nginx --since "5 minutes ago" --no-pager
```
Expected result after successful end-to-end configuration: NGINX returns to `active`, and webhook/Ansible logs show the playbook execution. Restore NGINX manually if the chain does not recover it:
```bash
sudo systemctl start nginx
```

## 4. Useful checks
```bash
curl -I http://127.0.0.1/
curl "http://localhost:9090/api/v1/targets"
curl -s http://localhost:9093/-/ready
```

## Repository layout
- `monitoring/docker-compose.yml` — Prometheus, Alertmanager and Blackbox Exporter.
- `monitoring/prometheus.yml` — scrape and probe configuration.
- `monitoring/alert.rules.yml` — NGINX-down alert rule.
- `monitoring/alertmanager.yml` — webhook receiver configuration.
- `webhook/app.py` — restricted webhook receiver.
- `ansible/restart-nginx.yml` — fixed Ansible recovery playbook.

## Scope and limitations
This is a local single-host demonstration, not production high availability. It monitors HTTP availability; CPU >90% alerting is not included in this minimal version. Add node_exporter and a CPU alert rule if CPU monitoring is required. Secure the webhook with authentication/TLS and restrict network access before any non-lab use.

## Verified work vs pending validation
Verified in the author's existing lab: Ansible setup run reported four successful tasks; systemd timer active; NGINX failure/recovery log included `RECOVERY SUCCESS`; `systemctl is-active nginx` returned `active`; local curl returned `HTTP/1.1 200 OK`.

Pending on the target VM: Docker monitoring stack startup, Prometheus target health, Alertmanager webhook delivery, and the complete Prometheus → Alertmanager → webhook → Ansible recovery test. Do not claim these integration tests passed until evidence is captured.
