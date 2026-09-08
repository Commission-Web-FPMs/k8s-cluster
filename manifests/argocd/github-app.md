# Application Github (dans l'orga)

Ajouter les credentials d'une APP de l'orga Github pour éviter les problèmes de Rate Limiting liés au polling des repos githubs.

## Instructions

- Créer une GitHub App dédiée, par exemple argocd, dans l’organisation GitHub.
- Lui donner seulement les permissions nécessaires. Pour le scmProvider, Metadata: Read-only suffit. Pour les webhook ajouter Content: Read-Only. (nécessaire pour le webhook push).

- Installer l’App uniquement sur les repositories publics à exposer à Argo CD. Éviter All repositories si tu veux qu’elle n’ait même pas accès aux métadonnées des repos privés.

- Récupérer les éléments permanents : App ID, Installation ID et la private key .pem. Il n’y a pas de PAT permanent associé à l’App. Argo génère des installation tokens temporaires à partir de cette clé. 

- Private Key : sur l'app. (à créer)
- Installation ID : dans l'org (id d'installation)
- App ID : sur l'app


### Créer le secret

```sh
kubectl create secret -n argocd generic github-app \
  --from-literal=url='https://github.com/Commission-Web-FPMs' \
  --from-literal=type='git' \
  --from-literal=githubAppID='123456' \
  --from-literal=githubAppInstallationID='12345678' \
  --from-file=githubAppPrivateKey='./argocd-app.private-key.pem' \
  --dry-run=client -o yaml \
| kubectl label --local -f - --dry-run=client -o yaml \
    # pas mettre repo-creds -> car dis utilise ça par défault pour les clones pour les clones (utile si repo privé)
    # argocd.argoproj.io/secret-type=repo-creds \
    app.kubernetes.io/part-of=argocd \
| kubeseal \
    --controller-namespace sealed-secrets \
    --format yaml \
> manifests/argocd/github-app.sealed.yaml
```

## Utiliser

Sur les ApplicationSet argo:
```
generators:
  - scmProvider:
      github:
        organization: Commission-Web-FPMs
        appSecretName: github-app
```