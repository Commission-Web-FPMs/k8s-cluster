# Credentials carte-fede main pour Authentik

Le SealedSecret `authentik-credentials`, dans `carte-fede-main`, contient
`AUTHENTIK_API_TOKEN` et `OIDC_CLIENT_SECRET`. Les valeurs correspondent à
[`carte-fede-credentials`](../../authentik/carte-fede-credentials.md), scellé
séparément pour le worker Authentik.

Le backend pourra charger ce Secret et la ConfigMap `authentik-config`
avec `envFrom`. Le chart et le code de carte-fede restent à adapter ; ce
Secret n'est pas encore consommé par son Deployment.

Pour la génération, la rotation et le contrat OIDC, suivre le
[guide carte-fede](../../../docs/authentik/carte-fede.md). Toute rotation doit
mettre à jour les deux SealedSecrets et redémarrer les consommateurs qui
chargent les clés en variables d'environnement. La reconstruction utilise
les fichiers scellés existants et la sauvegarde de la clé privée du contrôleur.
