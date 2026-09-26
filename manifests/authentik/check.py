"""Contrôle hors cluster : python3 manifests/authentik/check.py [CHART.tgz]."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml

root = Path(__file__).resolve().parents[2]
component = root / "manifests/authentik"
app = yaml.safe_load((component / "application.yaml").read_text())
source = app["spec"]["source"]
assert app["metadata"]["name"] == "authentik"
assert app["metadata"]["namespace"] == "argocd"
assert source["targetRevision"] == "2026.8.3"
assert source["helm"]["valuesObject"]["authentik"]["existingSecret"] == {
    "secretName": "authentik-secret"}
helm = os.environ.get("HELM", "helm")
kubectl = os.environ.get("KUBECTL", "kubectl")
chart = sys.argv[1] if len(sys.argv) > 1 else str(
    Path(tempfile.gettempdir()) / f"authentik-{source['targetRevision']}.tgz")

metadata = yaml.safe_load(subprocess.check_output([helm, "show", "chart", chart]))
assert metadata["version"] == source["targetRevision"]
with tempfile.TemporaryDirectory() as temporary:
    values = Path(temporary) / "values.yaml"
    values.write_text(yaml.safe_dump(source["helm"]["valuesObject"]))
    rendered = list(yaml.safe_load_all(subprocess.check_output([
        helm, "template", source["helm"]["releaseName"], chart,
        "--namespace", "authentik", "--values", str(values),
    ])))
rendered = [obj for obj in rendered if obj]
resources = list(yaml.safe_load_all(subprocess.check_output([
    kubectl, "kustomize", str(root / "manifests"),
])))
route = next(obj for obj in resources if obj["kind"] == "HTTPRoute"
             and obj["metadata"]["name"] == "authentik")
backend = route["spec"]["rules"][0]["backendRefs"][0]
service = next(obj for obj in rendered if obj["kind"] == "Service"
               and obj["metadata"]["name"] == backend["name"])
assert service["metadata"]["namespace"] == route["metadata"]["namespace"]
assert any(port["port"] == backend["port"] and port["targetPort"] == 9000
           for port in service["spec"]["ports"])
assert route["spec"]["parentRefs"] == [
    {"name": "public", "namespace": "traefik", "sectionName": "http"}]
assert route["spec"]["hostnames"] == ["auth.web.magellan.fpms.ac.be"]
assert not any(obj["kind"] in {"Secret", "StatefulSet", "PersistentVolumeClaim",
                              "Role", "RoleBinding", "ClusterRole",
                              "ClusterRoleBinding", "Ingress", "HTTPRoute"}
               for obj in rendered)
deployments = [obj for obj in rendered if obj["kind"] == "Deployment"]
assert {obj["metadata"]["name"] for obj in deployments} == {
    "authentik-server", "authentik-worker"}
for deployment in deployments:
    pod = deployment["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    container = pod["containers"][0]
    assert container["envFrom"] == [{"secretRef": {"name": "authentik-secret"}}]
    assert container["image"].endswith(":" + metadata["appVersion"])
    assert all(container.get(probe) for probe in
               ("startupProbe", "readinessProbe", "livenessProbe"))
    env = {item["name"]: item for item in container["env"]}
    for key in ("AUTHENTIK_SECRET_KEY", "AUTHENTIK_POSTGRESQL__PASSWORD"):
        ref = env[key]["valueFrom"]["secretKeyRef"]
        assert ref == {"name": "authentik-secret", "key": key}
    assert env["AUTHENTIK_POSTGRESQL__HOST"]["value"] == (
        "comweb-db-rw.comweb-db.svc.cluster.local")
    assert env["AUTHENTIK_POSTGRESQL__NAME"]["value"] == "authentik"
    assert env["AUTHENTIK_POSTGRESQL__USER"]["value"] == "authentik"
    assert env["AUTHENTIK_POSTGRESQL__SSLMODE"]["value"] == "require"
    assert container["resources"]["requests"]["memory"] == "512Mi"

database = next(obj for obj in resources if obj["kind"] == "Database"
                and obj["metadata"]["name"] == "authentik")
cluster = next(obj for obj in resources if obj["kind"] == "Cluster"
               and obj["metadata"]["name"] == "comweb-db")
assert database["spec"] == {"name": "authentik", "owner": "authentik",
                            "cluster": {"name": "comweb-db"},
                            "databaseReclaimPolicy": "retain"}
assert "bootstrap" not in cluster["spec"]
role = next(role for role in cluster["spec"]["managed"]["roles"]
            if role["name"] == database["spec"]["owner"])
assert role["passwordSecret"]["name"] == "authentik-db-credentials"
assert role["login"] and not any(role[key] for key in
                                ("superuser", "createdb", "createrole", "replication", "bypassrls"))
traefik = next(obj for obj in resources if obj["kind"] == "Application"
               and obj["metadata"]["name"] == "traefik")
ports = yaml.safe_load(traefik["spec"]["source"]["helm"]["values"])["ports"]
assert ports["web"]["forwardedHeaders"] == {"trustedIPs": ["172.17.0.1/32"]}
for namespace, name, keys in (
    ("authentik", "authentik-secret", {"AUTHENTIK_SECRET_KEY", "AUTHENTIK_POSTGRESQL__PASSWORD"}),
    ("comweb-db", "authentik-db-credentials", {"username", "password"}),
):
    sealed = next(obj for obj in resources if obj["kind"] == "SealedSecret"
                  and obj["metadata"]["name"] == name
                  and obj["metadata"]["namespace"] == namespace)
    assert set(sealed["spec"]["encryptedData"]) == keys
    assert all(value.startswith("Ag") for value in sealed["spec"]["encryptedData"].values())
    assert not {"data", "stringData"} & sealed["spec"]["template"].keys()
    assert not any("wide" in key for key in sealed["metadata"].get("annotations", {}))
print("OK : rendu Helm/Kustomize, route, secrets obligatoires, probes, RBAC et CNPG")
