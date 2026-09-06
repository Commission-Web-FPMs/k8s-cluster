---
service:      Application OAuth de l'organisation GitHub Commission-Web-FPMs
secret:       argocd-github-oauth
namespace:    argocd
portee:       lecture de l'appartenance aux équipes de l'organisation (read:org)
reemission:   Propriétaire de l'organisation GitHub
consomme_par: manifests/argocd/chart.yaml (configs.cm.dex.config)
---

# Connexion à ArgoCD par GitHub

## À quoi ça sert

ArgoCD délègue l'authentification à GitHub. Chacun se connecte
avec son propre compte, et **l'appartenance à une équipe de l'organisation
devient la source de vérité des droits** : retirer une personne de l'équipe
`comweb` sur GitHub lui retire son accès à ArgoCD, sans toucher au cluster.

Le chemin complet :

```text
   navigateur          ArgoCD (Dex)              GitHub
       │                    │                      │
       │  « je veux entrer »│                      │
       ├───────────────────►│                      │
       │                    │  clientID + secret   │
       │                    ├─────────────────────►│
       │                    │                      │
       │      « connectez-vous et autorisez »      │
       │◄─────────────────────────────────────────►│
       │                    │                      │
       │                    │◄─── équipes (slug) ──┤
       │                    │                      │
       │◄── session ArgoCD ─┤  policy.csv : g, Commission-Web-FPMs:comweb
       │   selon les rôles  │              → role:comweb
```

## 1. Créer l'application OAuth sur GitHub

1. `https://github.com/organizations/Commission-Web-FPMs/settings/applications`
2. **Developer settings → OAuth Apps → New OAuth App**
3. Remplir :

   | Champ | Valeur |
   | --- | --- |
   | Application name | `ArgoCD` |
   | Homepage URL | `https://argocd.example` |
   | Authorization callback URL | `https://argocd.example/api/dex/callback` |

4. **Register application**. GitHub affiche le **Client ID**.
5. **Generate a new client secret**, et copier la valeur immédiatement :
   elle n'est affichée qu'une seule fois.

## 2. Sceller le secret

La procédure générale et l'installation de `kubeseal` sont dans
[secrets.md](../../docs/secrets.md). Ici, deux clés :

```sh
kubectl create secret generic argocd-github-oauth \
  --namespace argocd \
  --from-literal=clientID='Ov23li...' \
  --from-literal=clientSecret='...' \
  --dry-run=client -o yaml \
| kubectl label --local -f - --dry-run=client -o yaml \
    app.kubernetes.io/part-of=argocd \
| kubeseal --controller-namespace sealed-secrets --format yaml \
> manifests/argocd/github-oauth.sealed.yaml
```
