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
```

### 2. Partie ArgoCD

ArgoCD s'ocucpe de maintenir et synchroniser les manifests présents dans ce repo github à jour dans le cluster.

L'installation s'effectue via un HelmChart géré par k0s. Une fois celui-ci installé, il configure argoCD, puis ajoute une application pointant vers `https://github.com/Commission-Web-FPMs/k8s-cluster.git` dossier `manifests/`.

```sh
# Appliquer le manifest
# Remarque: il faut changer l'url github dans le fichier avant si le repo est forké
kubectl apply -f manifests/argocd/chart.yaml
```


Comment accéder à ArgoCD? (admin)
```sh
# Récupérer le mdp admin
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# Forward le port 
kubectl -n argocd port-forward svc/argocd-server 8443:443

# ArgoCD est disponible localement (tant que le port-forward est actif)
# Sur https://localhost:8443
# Username: admin
# Password: (voir commande plus haut)
# NB: accepter le certificat "non trust" HTTPs
```