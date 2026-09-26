# Reprendre les Secrets Authentik existants

L’installation live utilise déjà ces deux Secrets. **Ne générer ni clé
Authentik ni mot de passe PostgreSQL** : cette procédure rescelle leurs données
actuelles, sans rotation et sans réinitialisation d’Authentik.

| Secret | Namespace | Clés attendues |
| --- | --- | --- |
| `authentik-secret` | `authentik` | `AUTHENTIK_SECRET_KEY`, `AUTHENTIK_POSTGRESQL__PASSWORD` |
| `authentik-db-credentials` | `comweb-db` | `username` = `authentik`, `password` = le même mot de passe |

Le second doit être de type `kubernetes.io/basic-auth`, pour
`Cluster.spec.managed.roles[].passwordSecret`. Le rôle SQL et la base
`authentik` existent déjà ; CNPG les réconcilie avec ces credentials.
Toutes les autres clés des Secrets sont conservées lors du rescellement.
Le chart charge aussi les autres clés de `authentik-secret` via `existingSecret`.

## Vérifier sans divulguer les credentials

Prérequis : Python 3, kubectl, kubeseal et accès au cluster existant. Exécuter
ce contrôle avant de synchroniser les manifests ; il ne modifie rien et ne
sort aucune valeur. Si les clés portent d’autres noms, adapter les références
Helm à l’existant ; ne pas créer de valeurs de remplacement.

```bash
python3 - <<'PYCODE'
import base64, json, subprocess

def secret(namespace, name):
    return json.loads(subprocess.check_output([
        "kubectl", "-n", namespace, "get", "secret", name, "-o", "json"
    ]))

app = secret("authentik", "authentik-secret")
db = secret("comweb-db", "authentik-db-credentials")
def value(obj, key):
    return base64.b64decode(obj["data"][key], validate=True)

assert value(app, "AUTHENTIK_SECRET_KEY"), "Clé Authentik absente ou vide"
assert value(app, "AUTHENTIK_POSTGRESQL__PASSWORD"), "Mot de passe SQL vide"
assert db["type"] == "kubernetes.io/basic-auth", "Type du Secret CNPG inattendu"
assert value(db, "username") == b"authentik", "Rôle SQL inattendu"
assert value(app, "AUTHENTIK_POSTGRESQL__PASSWORD") == value(db, "password"), "Les mots de passe diffèrent : arrêter la reprise"
print("OK : clé présente et credentials SQL concordants ; aucune valeur modifiée")
PYCODE
```

Valider aussi la connexion SQL avec les Pods actuels, selon
[le guide de reprise](../../docs/authentik.md#validation-sur-le-cluster).
Sauvegarder les valeurs d’origine dans le gestionnaire de mots de passe et
la clé privée Sealed Secrets selon [le guide commun](../../docs/secrets.md).

## Rescellement en lecture seule

L’inspection SSH a confirmé que les deux Secrets sont **déjà détenus par les
SealedSecrets de mêmes noms et namespaces**. Aucun `kubectl annotate`, patch de
Secret ou hook d’adoption n’est nécessaire. Les fichiers de cette branche sont
activés dans Kustomize. Les labels existants sont conservés, notamment
`cnpg.io/reload: "true"` pour les credentials CNPG.

Pour reproduire le rescellement depuis le poste de développement, utiliser
kubeseal **0.39.1**, comme le contrôleur live, et SSH déjà configuré. Ne lire
aucune clé privée. Les commandes suivantes ne modifient aucune ressource live :

```bash
(
  set -euo pipefail
  set +x
  umask 077
  sealed_tmp=$(mktemp -d)
  trap 'rm -rf "$sealed_tmp"' EXIT
  # Service public du contrôleur, accessible depuis le nœud ; aucune clé privée.
  ssh magellan@172.17.0.100 \
    'curl -fsS http://sealed-secrets-controller.sealed-secrets.svc.cluster.local:8080/v1/cert.pem' \
    > "$sealed_tmp/cert.pem"
  for target in authentik/authentik-secret comweb-db/authentik-db-credentials; do
    namespace=${target%/*}
    name=${target#*/}
    ssh magellan@172.17.0.100 \
      "sudo k0s kubectl -n $namespace get secret $name -o json" \
      | python3 -c '
import json, sys
s = json.load(sys.stdin)
m = s["metadata"]
# Exclure les métadonnées d’exécution et last-applied, qui peut contenir du clair.
json.dump({"apiVersion": "v1", "kind": "Secret", "type": s["type"],
    "metadata": {"name": m["name"], "namespace": m["namespace"],
                 "labels": m.get("labels", {})}, "data": s["data"]}, sys.stdout)
' \
      | kubeseal --cert "$sealed_tmp/cert.pem" --scope strict --format yaml \
      > "$sealed_tmp/$name.sealed.yaml"
  done
  mv "$sealed_tmp/authentik-secret.sealed.yaml" manifests/authentik/authentik-secret.sealed.yaml
  mv "$sealed_tmp/authentik-db-credentials.sealed.yaml" manifests/authentik/authentik-db-credentials.sealed.yaml
)
```

Si le nom du Service ne résout pas depuis le nœud, obtenir son ClusterIP avec
`sudo k0s kubectl -n sealed-secrets get svc sealed-secrets-controller` et utiliser
cette IP pour le GET du certificat. Lors de la reprise, l’IP était `10.96.227.46`.

Les données passent seulement en mémoire dans les tubes. Les fichiers générés
ne contiennent que les métadonnées publiques, le type du Secret et
`spec.encryptedData` ; aucun `data` ou `stringData` dans le template.
Ne pas copier les `ownerReferences`, UID ou annotations `last-applied` live.
Le scellement strict conserve exactement les noms et namespaces existants.

Le contrôleur a validé les deux ciphertexts via son endpoint de vérification
`POST /v1/verify` (sans application des ressources). Après chaque rescellement,
ce contrôle peut aussi se faire via `kubeseal --validate` avec un kubeconfig
configuré. Ne jamais utiliser `--recovery-unseal` ici : aucune clé privée
n’est nécessaire. Vérifier ensuite `python3 manifests/authentik/check.py`.

Les labels et la propriété des Secrets restent gérés par les mêmes
SealedSecrets après merge ; Argo CD gère leurs déclarations dans la racine.
Ne supprimer ni les Secrets ni les SealedSecrets existants. Aucun redémarrage
n’est nécessaire pour le rescellement seul, puisque les valeurs sont identiques.
La mise à jour 2026.8.3 entraîne son propre rollout.

Pour la validation effectuée ici : toutes les clés des deux Secrets ont été
comparées en mémoire avant/après scellement, et les UID n’ont pas changé.
L’égalité des deux mots de passe SQL a également été vérifiée. Aucun mot de
passe, clé Authentik ou autre donnée secrète n’a été changé ni affiché.
