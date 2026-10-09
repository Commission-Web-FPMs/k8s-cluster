# Signature des sessions de carte-fede main

Le Secret `carte-fede-backend-credentials` du namespace `carte-fede-main`
fournit `SECRET_KEY` au backend via `envFrom`. Flask utilise cette clé pour
signer les sessions et les jetons de réinitialisation des mots de passe.

La clé contient 32 octets aléatoires, encodés en hexadécimal. Le SealedSecret
conserve la même clé entre les workers, les réplicas et les redéploiements.
Ne pas la régénérer à chaque déploiement.

Pour remplacer la clé, exécuter depuis la racine du dépôt :

```sh
set -o pipefail
python3 - <<'PY' | kubeseal --controller-namespace sealed-secrets --scope strict --format yaml > manifests/projects/carte-fede/backend-credentials-main.sealed.yaml
import json
import secrets
import sys

json.dump({
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {
        "name": "carte-fede-backend-credentials",
        "namespace": "carte-fede-main",
    },
    "type": "Opaque",
    "stringData": {"SECRET_KEY": secrets.token_hex(32)},
}, sys.stdout)
PY
```

La valeur en clair passe uniquement dans le tube vers `kubeseal`.
Seul le fichier scellé est committé.

Après rotation, pousser le fichier scellé, attendre la synchronisation Argo CD
et redémarrer le backend pour recharger la clé. Les sessions et les jetons
signés avec l'ancienne clé deviennent invalides.
