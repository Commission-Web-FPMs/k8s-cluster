# Cluster Kubernetes (K8s) de la Comm Web

Ce dépôt GitHub contient l’ensemble des configurations du cluster [Kubernetes](https://kubernetes.io/) de la Commission Web de la Fédération des Étudiants de la Faculté Polytechnique de Mons. Il repose sur les principes du [GitOps](https://opengitops.dev/).

Il a pour vocation de contenir :

1. De la documentation et des guides d’utilisation à destination des étudiants afin de leur permettre de mettre en place, d’administrer et de maintenir le cluster Kubernetes.

2. Une configuration permettant de mettre en place l’état initial du cluster (« bootstrapping »).

3. Une configuration déclarative et versionnée décrivant l’état désiré du cluster.

4. Des outils permettant d’assurer les opérations courantes de maintenance.

## Documentation

1. [Topologie du cluster](./docs/topologie.md)
2. [Réseau](./docs/reseau.md)
3. [Sécurité et cloisonnement](./docs/securite.md)
4. [Gestion des secrets](./docs/secrets.md)
   - [Inventaire des secrets](./docs/secrets-inventaire.md)
5. [Améliorations prévues](./docs/backlog.md)

## Bootstrapping

Le bootstrapping initial s'effectue en deux parties:

1. Bootstrapper le cluster
2. Bootstrapper ArgoCD et l'application initiale, pointant vers ce repo github (`manifests/`)
 
### 1. Partie cluster

Pour boostrapper k8s (à faire une fois pour setup le cluster, ou le réparer):

```sh
# 1. Installer k0sctl
brew install k0sproject/tap/k0sctl # macos
winget install k0sproject.k0sctl # windows
# ...
```

```sh
# 2. Si utilisation d'un "bastion" car noeuds bloqués (skip si pas de bastion)
ssh-add ~/.ssh/id_ed25519

scp k0sctl.yaml magellan@bastion:

ssh -A magellan@bastion
# Installer k0sctl sur le bastion si nécessaire...
```

```sh
# 3. Apply la config
k0sctl apply -c k0sctl.yaml

# C'est terminé ! (littéralement)
```

```sh
# 4. Récupérer la config kubectl : 
mkdir -p ~/.kube
k0sctl kubeconfig > ~/.kube/config

# Si sur le bastion, transférer en local
scp magellan@bastion:.kube/config ~/.kube/config
```

```sh
# 5. Utiliser la config!
k0s kubectl # Si sur le noeud
kubectl # sinon (à installer)

# Si sur bastion
ssh -N -L 6443:172.17.0.100:6443 magellan@bastion # (valable sur une autre IP d'un des autres noeud aussi)
vim ~/.kube/config # modifer la config -> 172.17.0.100:6443 ->  127.0.0.1:6443
kubectl # Utiliser!

# Pour proxy: 

# linux
sed -i '/cluster:/a\    proxy-url: socks5://127.0.0.1:1080' ~/.kube/config

# macos
sed -i '' '/cluster:/a\
    proxy-url: socks5://127.0.0.1:1080' ~/.kube/config

# Puis
ssh -N -D 1080 magellan@bastion
```

### 2. Partie ArgoCD

ArgoCD s'occupe de maintenir et synchroniser les manifests présents dans ce repo github à jour dans le cluster.

```sh
# 1. Installation d'amorçage. (installer helm?!)
helm repo add argo https://argoproj.github.io/argo-helm && helm repo update argo

# 2. Installer ArgoCD (temporaire)
helm template argocd argo/argo-cd --version 10.8.0 -n argocd \
| kubectl apply -n argocd --server-side --force-conflicts \
    --field-manager=argocd-controller -f -

# 3. Installer le repo Github. À partir d'ici, plus rien à la main.
kubectl apply -f manifests/argocd/application.yaml
```

Comment accéder à ArgoCD? -> Utiliser son compte Github
```sh
# Forward le port 
kubectl -n argocd port-forward svc/argocd-server 8443:443

# https://localhost:8443
```