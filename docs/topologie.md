# Topologie du cluster

Cette page détaille la topologie du réseau.

Pour l'instant, le cluster est conçu et prévu pour tourner sur 3 machines (ou machines virtuelles) différentes en mode **High Availability (HA)**.

Ce choix découle principalement de deux raisons :

1. Le cluster utilise au minimum $N=3$ nœuds de control plane afin de pouvoir fonctionner en mode HA. Le datastore distribué nécessite un quorum de $\left\lfloor \frac{N}{2} \right\rfloor + 1$ nœuds. Avec 3 nœuds, le cluster peut donc continuer à fonctionner dans un état *dégradé* si un nœud tombe en panne.

2. Le cercle Magellan, où les VM sont actuellement hébergées, dispose de trois hyperviseurs physiques, ce qui permet d'associer une VM à chaque hyperviseur physique.

## Configuration réseau

> Cette partie nécessite un minimum de connaissances en réseaux informatiques. Il peut être intéressant de se référer au cours de BAC 3 de Patrice Mégret.

Chaque machine doit être adressable et doit pouvoir communiquer avec toutes les autres via le réseau.

La solution actuellement utilisée au sein du cercle Magellan repose sur un réseau Ethernet reliant les différents hyperviseurs. Chaque VM possède une interface réseau virtuelle avec sa propre adresse MAC et peut directement échanger des trames de couche 2 avec les autres VM.

Chaque VM possède une adresse IP appartenant au sous-réseau :

`172.17.0.0/24`

> Puisque les VM disposent déjà d'une connectivité de couche 2 entre elles, il est également possible de leur attribuer des adresses appartenant à un autre sous-réseau, avec un préfixe arbitraire. Par exemple : `ip addr add 10.67.67.1/24 dev ens18`.
>
> Cela permettrait de créer un réseau IP dédié aux communications entre les nœuds du cluster, tout en réutilisant l'infrastructure de couche 2 existante.

> Il est également possible de faire communiquer les VM au travers d'un réseau privé virtuel (VPN). Chaque nœud posséderait alors une adresse IP au sein du VPN. Cette solution permet notamment de chiffrer le trafic et d'intégrer des machines situées en dehors du réseau du Magellan.

> Enfin, si les adresses des machines sont directement routables entre elles, notamment via Internet, il est également possible d'utiliser directement ces adresses. Les ports nécessaires au fonctionnement du cluster doivent alors être accessibles entre les nœuds.
>
> Voici les principaux ports utilisés par les composants du cluster :
> La liste complète et à jour des ports utilisés par k0s est disponible dans la [documentation officielle de k0s](https://docs.k0sproject.io/head/networking/).
>
> | Protocole |  Port |
> | --------- | ----: |
> | TCP       |  2380 |
> | TCP       |  6443 |
> | TCP       |   179 |
> | TCP       | 10250 |
> | TCP       |  9443 |
> | TCP       |  8132 |
>
> Il est recommandé de limiter l'accès à ces ports aux seules adresses des autres nœuds du cluster à l'aide d'un pare-feu.

Prenons un exemple :

#### VM0 
- Hyperviseur : Hyperviseur1
- Hostname : k8s-dev-vm0
- Interface réseau : enp6s18
    - Addresse MAC: `bc:24:11:fb:63:27`
    - Addresse IP: `172.17.0.100/24`

#### VM1
- Hyperviseur : Hyperviseur2
- Hostname : k8s-dev-vm1
- Interface réseau : enp6s18
    - Addresse MAC: `bc:24:11:cd:8c:77`
    - Addresse IP: `172.17.0.101/24`

#### VM2
- Hyperviseur : Hyperviseur2
- Hostname : k8s-dev-vm2
- Interface réseau : enp6s18
    - Addresse MAC: `bc:24:11:43:b4:4c`
    - Addresse IP: `172.17.0.102/24`

Puisque les 3 VM sont dans le mêmes réseau de couche 2, elles peuvent s'envoyer des trames directement entre-elles (via leurs addresses MAC) sans devoir passer par un routeur (L3). L'addresse IP définie peut donc l'être de manière totalement arbitraire au sein de ce sous-réseau, pour peu que le masque de sous-réseau soit le même.

## Organisation Node+Worker

Chaque VM possède deux rôles k8s à la fois:
- Celui de control-plane
- Celui de worker