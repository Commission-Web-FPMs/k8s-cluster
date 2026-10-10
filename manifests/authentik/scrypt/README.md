# Carte Fédé: imported scrypt verifiers

Runtime pinned to Authentik 2026.8.2 / Django 5.2.17 and image digest
`sha256:ff8489a5af4f4fe415ffd180a8e3c10b120bc2592d13d79dac050d977f7b9ecd`.
The server and worker mount the two Python files through ConfigMap subPaths.
The chart pod annotation contains SHA-256 of `hashers.py` followed by
`user_settings.py`; recompute it for every settings change to trigger a rollout.

Authentik explicitly loads `/data/user_settings.py`. Its documentation labels
custom Python settings unsupported: every upgrade therefore requires an isolated
login/OIDC/restore/load regression test before changing the pinned version.
No upstream image is patched. No plaintext password or verifier belongs in Git.

The custom Django scrypt subclass only sets the OpenSSL verification ceiling to
128 MiB and retains N=32768, r=8, p=1. Werkzeug 64-byte digests are represented as
Django Base64 without changing their bytes or salts. The preferred native hasher
is Django Argon2 (time_cost=2, memory_cost=102400 KiB, parallelism=8 in this pinned
runtime). Native password changes and successful legacy logins use Argon2;
PBKDF2, PBKDF2-SHA1 and bcrypt verification remain available. This avoids a native
rehash from imported scrypt to preferred PBKDF2. No Carte Fédé password is changed.

Isolated tests cover ASCII/Unicode correct/wrong passwords, real authentication
flows and sessions, administrator/service credentials, password changes, signed
OIDC tokens, group access boundaries, disabled sessions, real import idempotence,
partial failure/resume and encrypted database recovery (230 tables).
At 4 concurrent clients / 8 complete logins, a 1 CPU / 1 GiB server succeeded;
maximum observed login latency was 7.989 s and cgroup memory peak 817037312 bytes.
A 768 MiB cap was reached, so production uses 1 GiB. This is a bounded small-load
validation, not a capacity guarantee for a mass login event.

Server: 1 Python worker, 2 threads, request 384 MiB, limit 1 GiB / 1 CPU,
RollingUpdate maxSurge=1/maxUnavailable=0. Worker: request 256 MiB, limit
768 MiB / 1 CPU, maxSurge=0/maxUnavailable=1. Background work may briefly pause
while the worker is replaced; the serving process remains available.
AUTHENTIK_LOG_LEVEL=warning prevents INFO events from printing identity details;
private Authentik audit events are retained in its database.

The dedicated migration role has global add_user only. Existing audit credentials are used strictly for GETs;
no permission of the existing application identity is broadened.
InitialPermissions grants view/change/reset_password on objects it creates;
no global password reset, delete, RBAC assignment, superuser or administrative
UI permission. Its API token expires after the tenant default (currently 1 day)
and must be revoked and its identity disabled by a separate GitOps commit after
verification. Existing application API credentials and roles are unchanged.

Rollback before imports: revert the settings commit after confirming no native
hash upgrades occurred. After imports: use the encrypted ownership journal and
scoped API identity to disable ONLY imported identities and remove their groups.
Keep Argon2 verification and preferred ordering if any hashes were upgraded;
never restore the old database over live Authentik or downgrade upgraded hashes.
If the custom scrypt verifier must be removed, use a forward correction retaining
Argon2 first and the built-in scrypt verifier, with imported accounts disabled.
Flask remains authoritative and enabled until a separately authorized OIDC switch.

Pending registrations are imported into existing `default` but DISABLED.
`default` already grants Carte Fédé access; never enable those identities merely
because they are in this group. They carry `carte_fede_pending_registration_uuid`,
not `carte_fede_uuid`: Flask approval currently creates a NEW user UUID. A verified
approval mapping must establish that new UUID before activation in membres.
Before OIDC, reconcile source password changes and new/deleted/approved identities;
never overwrite an Authentik-native password change without resolving the conflict.
Business ADMIN/VERIFIER/MEMBER roles and cards remain exclusively in PostgreSQL.

Worker probe validation, 11 October 2026: real isolated `ak healthcheck` probes, timeout 10 seconds / period 30 seconds, failure threshold 3 unchanged. Server retains HTTP health probes. Eight native login flows (four concurrent) passed, no OOM or new restart; server cgroup peak about 960 MiB under a 1 GiB limit. This is bounded validation, not capacity approval for opening OIDC to all members. Cold isolated startup took several minutes; startup probe retains 60 attempts.
