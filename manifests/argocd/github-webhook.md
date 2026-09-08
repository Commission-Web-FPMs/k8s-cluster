# Mise à jour via des Github Webhook

Possible de réutiliser l'app créée dans [github-app.md](./github-app.md); réutiliser celle-là.

## Instructions

- Modifier l'app sur github. Ajouter webhook: "active"
- URL: url publique argoCD et terminer par "/api/webhook" (exemple : `https://k8s-dev.magellan.fpms.ac.be/argocd/api/webhook`)
- Secret : générer une chaine aléatoire de caractère (`openssl rand -hex 32`)

### Installer le secret

```sh
kubectl create secret -n argocd generic github-webhook \
  --from-literal=webhook.github.secret='...' \
  --dry-run=client -o yaml \
| kubectl label --local -f - --dry-run=client -o yaml \
    app.kubernetes.io/part-of=argocd \
| kubeseal \
    --controller-namespace sealed-secrets \
    --format yaml \
> manifests/argocd/github-webhook.sealed.yaml
```