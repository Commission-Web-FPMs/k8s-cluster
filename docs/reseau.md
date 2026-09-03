# Réseau du cluster

Cette page explique le fonctionnement général du réseau Kubernetes utilisé par le cluster.

L'objectif n'est pas de détailler l'ensemble de l'implémentation réseau de Kubernetes, mais de donner une représentation suffisamment précise pour comprendre comment les nœuds et les Pods communiquent entre eux.

## Réseau des machines

Les trois machines du cluster appartiennent au même réseau :

`172.17.0.0/24`

Dans la configuration actuelle :

```text
                         Réseau Ethernet
                         172.17.0.0/24

             ┌────────────────┬────────────────┐
             │                │                │
             │                │                │
      172.17.0.100     172.17.0.101     172.17.0.102
          VM1               VM2               VM3
             │                │                │
             └────────────────┴────────────────┘
```

Les trois machines sont donc directement reliées au même réseau de couche 2.

Lorsqu'une machine souhaite envoyer un paquet à une autre, elle peut directement envoyer une trame Ethernet à son adresse MAC, sans passer par un routeur intermédiaire.

Par exemple :

```text
VM1                                      VM2
172.17.0.100 ───────────────────────► 172.17.0.101
                  Ethernet
```

Les adresses `172.17.0.100`, `172.17.0.101` et `172.17.0.102` sont les adresses des **nœuds Kubernetes** sur le réseau du Magellan.

Kubernetes utilise également des sous-réseaux IP destinés aux Pods.

## Réseau des Pods

Par défaut, k0s réserve le réseau suivant aux Pods :

`10.244.0.0/16`

Ce réseau est appelé le **Pod CIDR** du cluster.

Il est ensuite divisé entre les différents nœuds. Chaque nœud reçoit une partie du Pod CIDR et attribue des adresses de cette partie aux Pods qu'il héberge.

Par exemple :

```text
                           Réseau des machines
                            172.17.0.0/24

            ┌──────────────────┬──────────────────┐
            │                  │                  │
     172.17.0.100       172.17.0.101       172.17.0.102
          VM1                VM2                VM3
      ┌──────────┐        ┌──────────┐        ┌──────────┐
      │   Node   │        │   Node   │        │   Node   │
      │ routeur  │        │ routeur  │        │ routeur  │
      └────┬─────┘        └────┬─────┘        └────┬─────┘
           │                   │                   │
    10.244.1.0/24       10.244.2.0/24       10.244.3.0/24
           │                   │                   │
      ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
      │  Pods   │         │  Pods   │         │  Pods   │
      │ .2  .3  │         │ .2  .3  │         │ .2  .3  │
      └─────────┘         └─────────┘         └─────────┘
```

> Les sous-réseaux `10.244.1.0/24`, `10.244.2.0/24` et `10.244.3.0/24` sont utilisés ici comme exemple pour faciliter la représentation. Leur découpage exact est déterminé par la configuration du cluster.

Une manière simple de comprendre cette architecture est de considérer chaque nœud Kubernetes comme un **routeur entre deux réseaux** :

```text
                 Réseau des machines
                   172.17.0.0/24
                         │
                         │ 172.17.0.100
                    ┌────┴────┐
                    │   VM1   │
                    │         │
                    │ Routeur │
                    └────┬────┘
                         │
                         │
                   10.244.1.0/24
                         │
                       Pods
```

VM1 possède donc une interface vers le réseau `172.17.0.0/24` et permet également d'atteindre le sous-réseau `10.244.1.0/24` utilisé par ses Pods.

De la même manière :

```text
VM1 : 172.17.0.100  <->  10.244.1.0/24
VM2 : 172.17.0.101  <->  10.244.2.0/24
VM3 : 172.17.0.102  <->  10.244.3.0/24
```

Chaque nœud doit ensuite savoir par quel autre nœud passer pour atteindre les sous-réseaux des Pods qu'il n'héberge pas lui-même.

## Routage entre les nœuds

k0s utilise par défaut **kube-router** pour gérer le réseau Kubernetes.

Chaque nœud connaît le sous-réseau des Pods qu'il héberge et annonce cette information aux autres nœuds à l'aide du protocole **BGP**.

On peut imaginer que les nœuds s'échangent des informations équivalentes à :

```text
VM1 :
10.244.1.0/24 se trouve derrière 172.17.0.100

VM2 :
10.244.2.0/24 se trouve derrière 172.17.0.101

VM3 :
10.244.3.0/24 se trouve derrière 172.17.0.102
```

Les trois nœuds échangent ces informations entre eux :

```text
                        BGP

                VM1 ◄────────► VM2
                 ▲  \          / ▲
                 │   \        /  │
                 │    \      /   │
                 │     \    /    │
                 ▼      \  /     ▼
                        VM3
```

kube-router utilise ensuite ces informations pour configurer les routes du système Linux.

VM1 peut par exemple posséder des routes similaires à :

```text
10.244.2.0/24 via 172.17.0.101
10.244.3.0/24 via 172.17.0.102
```

Cela signifie simplement :

> Pour atteindre une adresse `10.244.2.x`, envoyer le paquet à VM2.

et :

> Pour atteindre une adresse `10.244.3.x`, envoyer le paquet à VM3.

BGP ne transporte donc pas le trafic des Pods. Il sert uniquement à permettre aux différents nœuds de **s'échanger leurs routes**.

## Communication entre deux Pods

Prenons deux Pods :

```text
Pod A : 10.244.1.5 sur VM1
Pod B : 10.244.2.8 sur VM2
```

Pod A souhaite envoyer un paquet à :

`10.244.2.8`

VM1 sait, grâce à sa table de routage, que le réseau `10.244.2.0/24` est accessible via VM2 :

```text
10.244.2.0/24 via 172.17.0.101
```

Le chemin est donc :

```text
     Pod A                    VM1                    VM2                   Pod B
  10.244.1.5            172.17.0.100           172.17.0.101          10.244.2.8
      │                       │                       │                     │
      └──────────────────────►│                       │                     │
                              └──────────────────────►│                     │
                                                      └────────────────────►│
```

Dans la topologie actuelle, les trois nœuds appartiennent au même sous-réseau `172.17.0.0/24`.

Le trafic entre leurs réseaux de Pods peut donc être transmis directement à l'aide du **routage IP classique de Linux**.

Le paquet IP peut conserver :

```text
Source      : 10.244.1.5
Destination : 10.244.2.8
```

Sur le réseau Ethernet, VM1 envoie simplement la trame à l'adresse MAC de VM2, puisque sa table de routage indique que VM2 est le prochain saut permettant d'atteindre `10.244.2.8`.

Il n'est donc pas nécessaire, dans cette topologie, d'encapsuler systématiquement le trafic dans un protocole tel que VXLAN.

> kube-router peut également utiliser une encapsulation IP-in-IP lorsque des nœuds se trouvent sur des sous-réseaux différents. Ce cas n'est pas nécessaire pour comprendre la topologie actuelle, où les trois VM appartiennent au même `172.17.0.0/24`.

## Nature du réseau des Pods

Le réseau des Pods peut être compris comme un ensemble de **sous-réseaux IP routés par les nœuds Kubernetes**.

Dans l'exemple précédent :

```text
10.244.1.0/24 -> VM1
10.244.2.0/24 -> VM2
10.244.3.0/24 -> VM3
```

Ces réseaux n'ont pas besoin d'être configurés sur le switch Ethernet du Magellan.

Ce sont les nœuds Kubernetes qui possèdent les interfaces et les routes nécessaires pour les atteindre.

On peut donc représenter l'ensemble comme un réseau routé classique :

```text
                         172.17.0.0/24

             ┌────────────────┬────────────────┐
             │                │                │
            VM1              VM2              VM3
             │                │                │
             │                │                │
      10.244.1.0/24    10.244.2.0/24    10.244.3.0/24
             │                │                │
           Pods             Pods             Pods
```

La principale différence avec un réseau routé configuré manuellement est que Kubernetes et kube-router automatisent l'attribution des réseaux et la distribution des routes.

## Plusieurs clusters sur le même réseau

Cette propriété a une conséquence intéressante.

Deux clusters Kubernetes différents peuvent être connectés au même réseau `172.17.0.0/24` tout en utilisant tous les deux le même Pod CIDR :

```text
                         172.17.0.0/24

           ┌──────────────────────┴──────────────────────┐
           │                                             │
      Cluster A                                     Cluster B
           │                                             │
     10.244.0.0/16                                 10.244.0.0/16
```

Ce n'est pas nécessairement un conflit.

Les routes vers `10.244.0.0/16` sont définies indépendamment dans les nœuds de chaque cluster.

Un nœud du cluster A peut donc considérer :

```text
10.244.2.8 = un Pod du cluster A
```

tandis qu'un nœud du cluster B peut considérer exactement la même adresse :

```text
10.244.2.8 = un Pod du cluster B
```

Les deux clusters possèdent simplement des **tables de routage différentes**.

Cela devient en revanche problématique si une machine ou un routeur extérieur doit pouvoir accéder simultanément aux Pods des deux clusters : une destination telle que `10.244.2.8` devient alors ambiguë.

Dans ce cas, il est préférable d'attribuer des Pod CIDR différents aux différents clusters.

Par exemple :

```text
Cluster A : 10.244.0.0/16
Cluster B : 10.245.0.0/16
```

## Accéder aux Pods depuis une autre machine

Les sous-réseaux des Pods peuvent également être routés depuis une machine extérieure au cluster.

Supposons une quatrième machine :

```text
Machine D : 172.17.0.50
```

Pour lui indiquer que le réseau `10.244.2.0/24` est accessible via VM2 :

```bash
ip route add 10.244.2.0/24 via 172.17.0.101
```

Machine D pourra alors envoyer directement des paquets vers un Pod tel que :

`10.244.2.8`

Le chemin devient simplement :

```text
Machine D                   VM2                     Pod
172.17.0.50            172.17.0.101            10.244.2.8
     │                       │                       │
     └──────────────────────►│──────────────────────►│
```

Le **routage** définit donc comment atteindre les Pods.

Les règles déterminant quelles communications sont autorisées constituent un problème différent. Kubernetes permet notamment de les définir à l'aide des ressources `NetworkPolicy`.

Une `NetworkPolicy` peut par exemple limiter un Pod afin qu'il n'accepte des connexions que depuis certains Pods, certains namespaces ou certaines plages d'adresses IP.

## Résumé

La topologie réseau peut donc être vue simplement de cette manière :

```text
                          172.17.0.0/24

              ┌────────────────┬────────────────┐
              │                │                │
       172.17.0.100     172.17.0.101     172.17.0.102
            VM1              VM2              VM3
         [routeur]         [routeur]         [routeur]
              │                │                │
       10.244.1.0/24     10.244.2.0/24     10.244.3.0/24
              │                │                │
           Pods VM1         Pods VM2         Pods VM3
```

Chaque nœud joue donc deux rôles du point de vue réseau :

1. Il est une machine du réseau `172.17.0.0/24`.
2. Il agit comme routeur vers le sous-réseau des Pods qu'il héberge.

**kube-router** permet aux différents nœuds d'échanger leurs routes avec **BGP**, tandis que Linux se charge ensuite du routage réel des paquets.

Dans la topologie actuelle, où les trois nœuds appartiennent au même réseau, les communications inter-nœuds peuvent ainsi utiliser directement le routage IP classique, sans nécessiter de VXLAN.

Pour plus de détails :

* [Documentation réseau de k0s](https://docs.k0sproject.io/head/networking/)
* [Documentation de kube-router](https://www.kube-router.io/)
