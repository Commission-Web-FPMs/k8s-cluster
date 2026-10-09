# Credentials Authentik de carte-fede main

Le SealedSecret `carte-fede-credentials`, dans `authentik`, contient
`AUTHENTIK_API_TOKEN` et `OIDC_CLIENT_SECRET`. Le worker et le Job de
provisionnement les montent sous `/secrets/carte-fede`. Le blueprint lit ces
fichiers pour définir le token API et le secret du provider OIDC.

Les mêmes valeurs sont scellées séparément dans
[`authentik-credentials-main.sealed.yaml`](../projects/carte-fede/authentik-credentials-main.sealed.yaml)
pour le namespace `carte-fede-main`. Les noms et namespaces sont liés au
scellement strict : les fichiers chiffrés ne sont pas interchangeables.

La génération et la rotation sont décrites dans le
[guide carte-fede](../../docs/authentik/carte-fede.md). Pour reconstruire,
restaurer la clé privée Sealed Secrets puis laisser Argo CD synchroniser les
fichiers existants. Régénérer des clés changerait les credentials du service.

Ne pas appliquer de rotation manuelle dans l'interface Authentik sans mettre
à jour les deux SealedSecrets : le blueprint rétablirait la valeur de Git.
