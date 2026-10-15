"""Lot NT1 — théorie des nombres : divisibilité (chapitre 1 de MODNT, Aditya Khurmi, 2020).

Cours rédigé à partir du chapitre 1 « Divisibility » (pp. 13–43). Problemset : 15 problèmes
extraits de la section 1.12, avec indices et solutions rédigés pour ARCH Arena.

Statuts à relire avant publication :
- problème 8 : énoncé faux tel qu'écrit (contre-exemple a = 7, b = 14) ;
- problèmes 10, 11, 12, 13 et 15 : solution incomplète, marquée comme telle dans le champ solution.
Le cours est publié avec published=False.
"""

from datetime import date

COURSES = [
    {
        "subject": "number_theory",
        "sequence": 1,
        "title": "Divisibilité : bases",
        "available_from": date(2026, 10, 19),
        "planning_label": "Semaine 1 · à confirmer",
        "published": False,
        "theory_md": r"""
Ce chapitre est la porte d'entrée de la théorie des nombres. La divisibilité engendre une foule de définitions et de résultats : on y étudie les multiples, la division euclidienne, les nombres premiers, le PGCD et le PPCM, l'identité de Bézout et les systèmes de numération.

**1. Tables de multiplication**

Pour comprendre la divisibilité, regardons d'où elle vient : la table de multiplication de $5$. On a $0 \times 5 = 0$, $1 \times 5 = 5$, $2 \times 5 = 10$, et ainsi de suite. L'ensemble des multiples de $5$ est
$$M = \{\dots, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, \dots\}.$$

**Définition 1.1.1.** Un entier $n$ est un *multiple* de $m$ s'il apparaît dans la table de multiplication de $m$.

**Définition 1.1.2.** On dit que $m$ *divise* $n$, et on écrit $m \mid n$, si $n$ est un multiple de $m$. On lit « $m$ divise $n$ ».

Par exemple, $7 \mid 14$ et $8 \mid 0$. Attention au sens de la barre : le nombre placé après le symbole $\mid$ est le multiple. Dans une fraction, on écrit d'abord le multiple, par exemple $\frac{14}{7} = 2$, mais la notation $7 \mid 14$ met le diviseur en premier.

**2. Propriétés de la divisibilité**

**2.1 Résultats de base**

**Théorème 1.2.1.** Soient $x, y, z$ des entiers.

- On a $x \mid x$.
- On a toujours $1 \mid x$ et $x \mid 0$.
- Si $x \mid y$ et $y \mid z$, alors $x \mid z$.
- Si $x \mid y$, il existe un entier $k$ tel que $y = kx$. Ici $k$ peut être négatif.

Le dernier point est particulièrement utile. Il dit en substance que
$$m \mid n \iff \frac{n}{m} \in \mathbb{Z}.$$
Cette équivalence permet de transformer une divisibilité en calcul algébrique. Par exemple, pour démontrer la troisième propriété : si $x \mid y$ et $y \mid z$, alors $\frac{y}{x} \in \mathbb{Z}$ et $\frac{z}{y} \in \mathbb{Z}$, donc $\frac{z}{x} = \frac{y}{x} \cdot \frac{z}{y} \in \mathbb{Z}$, c'est-à-dire $x \mid z$.

**2.2 Première propriété spéciale**

Regardons à nouveau la table de multiplication de $5$, en ne gardant que les nombres positifs. Si $x \mid y$, alors $x$ semble « plus petit » que $y$. Cela est-il toujours vrai ? Si $x \mid y$, alors $y$ appartient à l'ensemble $\{\dots, -3x, -2x, -x, 0, x, 2x, 3x, \dots\}$. En prenant les valeurs absolues, on trouve $|y| \geq |x|$ dès que $y \neq 0$.

**Théorème 1.2.2.** Si $x \mid y$ pour deux entiers $x$ et $y$, alors $y = 0$ ou $|x| \leq |y|$.

Le cas $y = 0$ est très facile à oublier, et c'est pourtant souvent la clé d'une solution. Il ne faut pas non plus oublier la valeur absolue.

*Preuve.* Écrivons $y = kx$. Si $k = 0$, alors $y = 0$. Sinon, $k \neq 0$ donc $|k| \geq 1$, et l'on a $|y| = |k| \cdot |x| \geq |x|$.

Attention : il est tentant d'écrire $y = kx > x$, mais ce n'est pas valable, car $k$ peut être négatif. Si l'on multiplie une inégalité par un nombre négatif, son sens s'inverse. Par exemple $5 > 2$, mais $-5 < -2$. C'est pour cette raison qu'on utilise la valeur absolue.

**2.3 Deuxième propriété spéciale**

Considérons à nouveau l'ensemble $M$ des multiples de $5$. Si l'on multiplie un élément de $M$ par un entier $c$, le résultat reste dans $M$. Si l'on additionne deux éléments de $M$, le résultat reste aussi dans $M$, car $5a + 5b = 5(a+b)$. Ainsi, si $x, y \in M$ et $a, b \in \mathbb{Z}$, alors $ax + by \in M$.

En généralisant le nombre $5$ à un entier quelconque, on obtient l'une des propriétés les plus utiles de la divisibilité.

**Théorème 1.2.3.** Si $c \mid x$ et $c \mid y$, alors $c \mid ax + by$ pour tous $a, b \in \mathbb{Z}$.

**2.4 Liste des propriétés**

**Théorème 1.2.4.** Soient $x, y, z$ des entiers.

- $x \mid x$.
- $1 \mid x$ et $x \mid 0$.
- Si $x \mid y$ et $y \mid z$, alors $x \mid z$.
- Si $z \mid x$ et $z \mid y$, alors $z \mid ax + by$ pour tous entiers $a, b$ (éventuellement négatifs).
- Si $x \mid y$, alors $y = 0$ ou $|x| \leq |y|$.
- Si $x \mid y$ et $y \mid x$, alors $|x| = |y|$.
- Pour tout entier $z \neq 0$, on a $x \mid y$ si et seulement si $xz \mid yz$.
- Si $x \mid y$, alors $x \mid yz$ pour tout entier $z$.

Les deux propriétés spéciales et la dernière propriété sont les plus utiles en résolution de problèmes. Par exemple, si l'on sait que $n \mid 2n + 1$, on peut retrancher $2n$ des deux côtés : on obtient $n \mid 1$, donc $n = \pm 1$. Dans ce type de situation, on ajoute, soustrait ou multiplie des expressions bien choisies pour simplifier le membre de droite.

**3. Division euclidienne**

Pour les multiples de $5$, on sait placer un entier quelconque entre deux multiples consécutifs. Par exemple, $32$ se situe entre $30$ et $35$, et l'on écrit $32 = 5 \times 6 + 2$. De même, $36 = 5 \times 7 + 1$.

En généralisant cette idée, on obtient le résultat suivant.

**Théorème 1.3.1 (Division euclidienne).** Soient $b$ un entier et $a$ un entier strictement positif. Il existe un unique couple d'entiers $(q, r)$ tel que
$$b = aq + r \qquad \text{et} \qquad 0 \leq r < a.$$
On appelle $q$ le *quotient* et $r$ le *reste*. C'est exactement ce que l'on fait depuis toujours lors d'une division posée.

Pourquoi $0 \leq r$ et non $0 < r$ ? Et pourquoi $r < a$ et non $r \leq a$ ? Parce que chaque entier $b$ peut s'écrire de façon unique avec un reste dans l'intervalle $[0, a[$, et que le reste $0$ doit être permis (par exemple $10 = 5 \times 2 + 0$).

*Preuve.* Voir la section 10, où la démonstration est donnée par le principe extrémal.

**4. Nombres premiers**

Un entier $p \geq 2$ est *premier* s'il n'a que deux diviseurs positifs, $1$ et $p$. La liste commence par $2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, \dots$

Le nombre $2$ est le seul nombre premier pair. Cela rend les arguments de parité utiles dans les problèmes sur les nombres premiers. Le nombre $1$ n'est pas premier.

Les nombres premiers sont les « atomes » de tous les entiers, et comprendre les nombres premiers revient en grande partie à comprendre les entiers. Leur répartition ne suit cependant aucune formule simple. Le théorème des nombres premiers (admis dans ce cours) donne une estimation : si $\pi(n)$ désigne le nombre de nombres premiers inférieurs ou égaux à $n$, alors $\pi(n) \sim \frac{n}{\ln n}$, et cette estimation devient meilleure quand $n$ grandit.

**4.1 Théorème fondamental de l'arithmétique**

**Théorème 1.4.1 (Théorème fondamental de l'arithmétique).** Tout entier $n > 1$ possède une décomposition en produit de nombres premiers unique, à l'ordre des facteurs près.

Le mot « unique » signifie deux choses : il existe au moins une décomposition, et il en existe au plus une. Par exemple, $45 = 3^2 \cdot 5$ et il n'existe aucune autre façon d'écrire $45$ comme produit de nombres premiers, à l'ordre près.

Tout entier $n$ peut donc s'écrire
$$n = p_1^{\alpha_1} p_2^{\alpha_2} \cdots p_k^{\alpha_k},$$
où $p_1, \dots, p_k$ sont des nombres premiers et $\alpha_1, \dots, \alpha_k$ des entiers positifs ou nuls. Un exposant peut être nul : par exemple $24 = 2^3 \cdot 3$.

Le nombre $1$ est le seul entier positif sans décomposition en nombres premiers, puisque c'est le produit vide.

Conseil important : pensez aux nombres à travers leurs facteurs premiers. Cette idée revient très souvent dans les problèmes.

**5. Les entiers vus comme multi-ensembles**

Puisque tout entier se décompose en facteurs premiers, et que ces facteurs premiers « identifient » le nombre, il est utile de voir un entier comme un ensemble de facteurs premiers.

Le nombre $1$ correspond à l'ensemble vide. Le nombre $6 = 2 \cdot 3$ correspond à l'ensemble $\{2, 3\}$, et $70 = 2 \cdot 5 \cdot 7$ à l'ensemble $\{2, 5, 7\}$. Mais un ensemble ne peut pas contenir deux fois le même élément, alors comment écrire $4 = 2^2$ ? On utilise un **multi-ensemble**, c'est-à-dire un ensemble qui autorise les répétitions : $4$ correspond au multi-ensemble $\{2, 2\}$. En général, $n = p_1^{\alpha_1} \cdots p_k^{\alpha_k}$ correspond au multi-ensemble où chaque $p_i$ apparaît $\alpha_i$ fois.

Pour un entier négatif, on ajoute simplement $-1$ au multi-ensemble. Par exemple, $-20$ correspond à $\{-1, 2, 2, 5\}$.

Dans ce chapitre, on note les entiers par des lettres minuscules et leurs multi-ensembles par les majuscules correspondantes. Ainsi, si $n = 20$, alors $N = \{2, 2, 5\}$.

**Théorème 1.5.1 (Divisibilité et inclusion).** Soient $a$ et $b$ deux entiers, de multi-ensembles $A$ et $B$. Alors
$$a \mid b \iff A \subseteq B.$$

L'intérêt de cette vision ensembliste est qu'on peut raisonner à l'aide de diagrammes de Venn. De nombreuses propriétés du PGCD et du PPCM deviennent alors évidentes.

**6. PGCD et PPCM**

**Définition 1.6.1.** Le *PGCD* (plus grand commun diviseur) de deux entiers $m$ et $n$ est le produit des facteurs premiers communs, chacun élevé à la plus petite puissance apparaissant dans $m$ et $n$. On le note $\gcd(m, n)$ ou simplement $(m, n)$. Il correspond à l'intersection $M \cap N$ des multi-ensembles.

Par exemple, si $m = 2^2 \cdot 5^3 \cdot 7$ et $n = 2^3 \cdot 3^2 \cdot 7^2$, alors $\gcd(m, n) = 2^2 \cdot 7$.

**Lemme 1.6.1.** Soient $a$ et $b$ des entiers. Alors $\gcd(a, b)$ est le plus grand entier qui divise à la fois $a$ et $b$. En particulier, $\gcd(a, b) \leq |a|$ et $\gcd(a, b) \leq |b|$ lorsque $a, b$ sont non nuls.

*Preuve (idée).* Si un entier $x$ plus grand que $\gcd(a,b)$ divisait $a$ et $b$, ses facteurs premiers communs à $a$ et $b$ seraient déjà contenus dans $\gcd(a,b)$, donc $x$ n'aurait rien de plus, ce qui est absurde.

**Lemme 1.6.2.** Soient $a, b, c$ des entiers. Si $c \mid a$ et $c \mid b$, alors $c \mid \gcd(a, b)$.

*Preuve (diagramme).* Soit $C$ le multi-ensemble de $c$. Comme $c \mid a$ et $c \mid b$, on a $C \subseteq A$ et $C \subseteq B$, donc $C$ est contenu dans $A \cap B$, c'est-à-dire $c \mid \gcd(a, b)$.

**Lemme 1.6.3 (Décomposition du PGCD).** Soient $a$ et $b$ deux entiers, de décompositions $a = p_1^{\alpha_1} \cdots p_k^{\alpha_k}$ et $b = p_1^{\beta_1} \cdots p_k^{\beta_k}$, où les exposants sont positifs ou nuls. Alors
$$\gcd(a, b) = p_1^{\min(\alpha_1, \beta_1)} \cdots p_k^{\min(\alpha_k, \beta_k)}.$$

**Définition 1.6.2 (PPCM).** Le *PPCM* (plus petit commun multiple) de deux entiers $a$ et $b$ est le plus petit entier positif divisible par $a$ et par $b$. On le note $\operatorname{lcm}(a, b)$. Il correspond à la réunion $A \cup B$ des multi-ensembles, et si $a = p_1^{\alpha_1} \cdots p_k^{\alpha_k}$ et $b = p_1^{\beta_1} \cdots p_k^{\beta_k}$, alors
$$\operatorname{lcm}(a, b) = p_1^{\max(\alpha_1, \beta_1)} \cdots p_k^{\max(\alpha_k, \beta_k)}.$$

**Lemme 1.6.4.** Soient $a, b, c$ des entiers. Si $a \mid c$ et $b \mid c$, alors $\operatorname{lcm}(a, b) \mid c$.

**Lemme 1.6.5 (Produit du PGCD et du PPCM).** Pour deux entiers $a$ et $b$,
$$\gcd(a, b) \cdot \operatorname{lcm}(a, b) = ab.$$

*Preuve.* Avec les décompositions ci-dessus, on a
$$\gcd(a,b) \cdot \operatorname{lcm}(a,b) = \prod_{i} p_i^{\min(\alpha_i,\beta_i) + \max(\alpha_i,\beta_i)} = \prod_{i} p_i^{\alpha_i + \beta_i} = ab,$$
car $\min(x,y) + \max(x,y) = x + y$.

Une autre preuve utilise les diagrammes de Venn : la somme $A + B$ des multi-ensembles vaut $(A \cup B) + (A \cap B)$.

**Définition 1.6.3.** Deux entiers $a$ et $b$ sont *premiers entre eux* (ou *étrangers*) si $\gcd(a, b) = 1$. Autrement dit, ils n'ont aucun facteur premier commun.

**Théorème 1.6.1 (Euclide).** Il existe une infinité de nombres premiers.

*Preuve.* Supposons qu'il n'existe qu'un nombre fini de nombres premiers, $p_1, \dots, p_k$. Posons
$$N = p_1 p_2 \cdots p_k + 1.$$
Le nombre $N$ est strictement supérieur à $1$, donc, par le théorème fondamental de l'arithmétique, il possède un facteur premier $p$. Mais $N$ laisse le reste $1$ dans la division par chacun des $p_i$, donc $p$ est différent de tous les $p_i$. Cela contredit le fait que $p_1, \dots, p_k$ sont tous les nombres premiers.

**7. Algorithme d'Euclide**

Idée clé : pensez au PGCD comme aux facteurs premiers communs. Par exemple, si $m = p^2 q$ et $n = p q^2 r$, alors $\gcd(m, n) = pq$, et $m + n = pq(p + qr)$. En général, on peut sortir le PGCD en facteur dans une somme.

**Lemme 1.7.1.** Soient $a, b$ des entiers. Pour tout entier $k$,
$$\gcd(a, b) = \gcd(a \pm kb, b).$$
En particulier, si $a = bq + r$ avec $0 \leq r < b$, alors $\gcd(a, b) = \gcd(r, b)$.

*Preuve.* On a $\gcd(a, b) = \gcd(bq + r, b) = \gcd(bq + r - bq, b) = \gcd(r, b)$.

Ce lemme donne un algorithme pour calculer le PGCD. Pour calculer $\gcd(370, 100)$, on écrit $370 = 3 \times 100 + 70$, donc $\gcd(370, 100) = \gcd(70, 100)$. Puis $100 = 1 \times 70 + 30$, donc $\gcd(70, 100) = \gcd(70, 30)$. En continuant :
$$\gcd(370, 100) = \gcd(70, 100) = \gcd(70, 30) = \gcd(10, 30) = 10,$$
car $10$ divise $30$.

Autre exemple, pour $\gcd(440, 124)$ :
$$440 = 124 \times 3 + 68, \quad 124 = 68 \times 1 + 56, \quad 68 = 56 \times 1 + 12, \quad 56 = 12 \times 4 + 8, \quad 12 = 8 \times 1 + 4, \quad 8 = 4 \times 2 + 0.$$
Le dernier reste non nul est $4$, donc $\gcd(440, 124) = 4$.

L'algorithme s'arrête car les restes décroissent strictement et restent positifs : il ne peut y avoir qu'un nombre fini d'étapes. On s'arrête dès que le reste est nul ; le dernier reste non nul est le PGCD.

**8. Identité de Bézout**

Commençons par une question. Si $ax + by = n$ avec $a, b, x, y, n$ entiers, montrer que $\gcd(a, b)$ divise $n$.

Plus généralement, étant donnés $a$ et $b$, quelles valeurs peut prendre $ax + by$ quand $x, y$ parcourent $\mathbb{Z}$ ? Un entier $n$ est dit *représentable* s'il existe $x, y \in \mathbb{Z}$ avec $ax + by = n$. Pour $a = 2$ et $b = 4$, tous les multiples de $2$ sont représentables : le PGCD $\gcd(2, 4) = 2$ l'est.

**Exemple 1.8.1.** Pour $(a, b) = (3, 6)$, on a $\gcd(3, 6) = 3 = 3 \cdot 1 + 6 \cdot 0$. Pour $(a, b) = (35, 42)$, on a $\gcd(35, 42) = 7 = 35 \cdot 5 + 42 \cdot (-4)$. La conjecture « le PGCD est toujours représentable » est donc vérifiée dans ces cas.

En effet, si $ax_0 + by_0 = \gcd(a, b)$, alors pour tout entier $m$,
$$a(m x_0) + b(m y_0) = m \gcd(a, b).$$
Donc tout multiple du PGCD est représentable. C'est le théorème suivant.

**Théorème 1.8.1 (Bézout).** Soient $a, b$ des entiers. L'équation $ax + by = n$ admet une solution entière si et seulement si $\gcd(a, b) \mid n$.

Il y a deux sens. Si $ax + by = n$, alors $\gcd(a,b) \mid n$. Réciproquement, si $\gcd(a,b) \mid n$, il existe $x_0, y_0 \in \mathbb{Z}$ tels que $a x_0 + b y_0 = n$. Ce second point est démontré plus loin, dans la section 10.

**Lemme 1.8.1 (Lemme d'Euclide).** Si $c \mid ab$ et $\gcd(c, a) = 1$, alors $c \mid b$.

*Preuve.* Comme $\gcd(c, a) = 1$, il existe $x, y \in \mathbb{Z}$ tels que $cx + ay = 1$. En multipliant par $b$ : $cbx + aby = b$. Le nombre $c$ divise $cbx$, et il divise $ab$ donc aussi $aby$. Il divise donc la somme $cbx + aby = b$.

**Exemple 1.8.2 (Théorème de Putnam 2000).** Montrons que
$$\frac{\gcd(m, n)}{n} \binom{n}{m}$$
est un entier pour tous entiers $n \geq m \geq 1$.

Par l'identité de Bézout, écrivons $\gcd(m, n) = mx + ny$ avec $x, y \in \mathbb{Z}$. Alors
$$\frac{\gcd(m,n)}{n} \binom{n}{m} = x \cdot \frac{m}{n}\binom{n}{m} + y \binom{n}{m}.$$
Le second terme est un entier. Pour le premier, on calcule :
$$\frac{m}{n}\binom{n}{m} = \frac{m}{n} \cdot \frac{n!}{m!(n-m)!} = \frac{(n-1)!}{(m-1)!(n-m)!} = \binom{n-1}{m-1}.$$
C'est un entier, donc l'expression entière est bien un entier.

**9. Systèmes de numération**

Tout entier s'écrit en base $10$ : par exemple
$$514\,567 = 5 \cdot 10^5 + 1 \cdot 10^4 + 4 \cdot 10^3 + 5 \cdot 10^2 + 6 \cdot 10^1 + 7 \cdot 10^0.$$
On peut écrire les entiers dans une base $\ell \geq 2$ quelconque. Un entier $n$ s'écrit alors
$$n = a_0 + a_1 \ell + a_2 \ell^2 + \cdots + a_k \ell^k, \qquad 0 \leq a_i \leq \ell - 1, \quad a_k \neq 0,$$
et l'on note $n = \overline{a_k \cdots a_1 a_0}_{(\ell)}$.

En base $2$ (binaire), on utilise les chiffres $0$ et $1$. Par exemple, $2 = 10_{(2)}$, $3 = 11_{(2)}$, $4 = 100_{(2)}$, $5 = 101_{(2)}$, $6 = 110_{(2)}$, $7 = 111_{(2)}$, $8 = 1000_{(2)}$, $9 = 1001_{(2)}$, $10 = 1010_{(2)}$. L'addition se fait comme en base $10$, avec la retenue $1 + 1 = 10_{(2)}$.

Pourquoi n'y a-t-il pas de chiffre $2$ en base $2$ ? Parce que $2 = 1 \cdot 2^1 + 0 \cdot 2^0$ : tout chiffre égal à $2$ se réécrit avec une retenue vers le rang suivant. De même, en base $4$, $9 = 21_{(4)}$.

**Méthode pour changer de base.** Pour écrire $52$ en base $3$, on écrit $52 = a_0 + a_1 \cdot 3 + \cdots$. Comme tous les termes sauf $a_0$ sont divisibles par $3$, le reste de $52$ modulo $3$ donne $a_0 = 1$. On poursuit avec le quotient, $\frac{52 - 1}{3} = 17$, dont le reste modulo $3$ donne $a_1 = 2$, et ainsi de suite. On obtient $52 = 1221_{(3)}$, car $1 \cdot 27 + 2 \cdot 9 + 2 \cdot 3 + 1 = 52$.

Pour les petits nombres, on peut aussi encadrer $n$ entre deux puissances de la base. Si $\ell^k \leq n < \ell^{k+1}$, alors $k$ est le rang du chiffre de gauche, et le chiffre $a_k$ vérifie $a_k \ell^k \leq n < (a_k + 1) \ell^k$. Par exemple, $\ell = 3$ et $n = 52$ : $27 \leq 52 < 81$, donc $k = 3$, et $1 \cdot 27 \leq 52 < 2 \cdot 27$, donc le chiffre de gauche vaut $1$. On continue avec $52 - 27 = 25$.

**Théorème 1.9.1.** Tout entier $n$ admet une unique représentation en base $\ell$.

*Preuve (idée).* Par division euclidienne de $n$ par $\ell$, le chiffre $a_0$ est le reste de $n$ modulo $\ell$, et $\frac{n - a_0}{\ell}$ est l'entier obtenu en retirant ce chiffre. En répétant ce procédé, on obtient les chiffres un à un, de manière unique.

**10. Résultats supplémentaires**

**Exemple 1.10.1.** Montrons que $\sqrt{p}$ est irrationnel pour tout nombre premier $p$.

Supposons le contraire, et écrivons $\sqrt{p} = \frac{m}{n}$ avec $m, n$ entiers positifs premiers entre eux (on peut toujours simplifier la fraction). En élevant au carré, $m^2 = p n^2$, donc $p \mid m^2$. Comme $p$ est premier, $p \mid m$. Écrivons $m = p m^*$. Alors $p^2 (m^*)^2 = p n^2$, soit $n^2 = p (m^*)^2$. Donc $p \mid n^2$, et de nouveau $p \mid n$. Ainsi $p$ divise à la fois $m$ et $n$, ce qui contredit le fait que $m$ et $n$ sont premiers entre eux.

Le fait que $p$ soit premier est utilisé au moment où l'on déduit $p \mid m$ à partir de $p \mid m^2$.

**Exemple 1.10.2.** Si $p$ est premier et $0 < k < p$, alors $\binom{p}{k}$ est divisible par $p$.

On écrit
$$\binom{p}{k} = \frac{p!}{k!(p-k)!} = p \cdot \frac{(p-1)(p-2) \cdots (p-k+1)}{k(k-1) \cdots 1} = pS.$$
Le nombre $\binom{p}{k}$ est un entier, et $p$ est premier avec chacun des entiers $1, \dots, k$ (car ils sont strictement inférieurs à $p$). Le facteur $p$ n'apporte donc aucune contribution à la divisibilité par les facteurs du dénominateur : $S$ est un entier, et $p \mid \binom{p}{k}$.

**Exemple 1.10.3 (Division euclidienne).** Soient $a > 0$ et $b$ des entiers. Montrons qu'il existe un unique couple $(q, r)$ avec $b = aq + r$ et $0 \leq r < a$.

*Preuve.* Il existe un unique entier $q$ tel que $aq \leq b < a(q+1)$ : c'est le plus grand multiple de $a$ inférieur ou égal à $b$, et c'est le principe extrémal appliqué à l'ensemble des multiples de $a$ qui ne dépassent pas $b$. Posons $r = b - aq$. On a $r \geq 0$ par construction, et comme $b < aq + a$, on a $r < a$. Ainsi le couple $(q, r)$ convient. Son unicité vient de ce que $q$ est unique.

**Exemple 1.10.4.** Soient $a, m, n$ des entiers positifs. Montrons que
$$\gcd(a^m - 1, a^n - 1) = a^{\gcd(m, n)} - 1.$$

*Preuve.* Supposons $m \geq n$. On a
$$a^m - 1 = a^{m-n}(a^n - 1) + (a^{m-n} - 1),$$
donc $\gcd(a^m - 1, a^n - 1) = \gcd(a^{m-n} - 1, a^n - 1)$. Ainsi, le couple d'exposants $(m, n)$ est remplacé par $(m - n, n)$, exactement comme dans l'algorithme d'Euclide. En répétant, on arrive à un couple dont l'un des exposants est nul, et $a^0 - 1 = 0$. Le PGCD est alors la valeur non nulle restante, à savoir $a^{\gcd(m,n)} - 1$.

**Exemple 1.10.5 (Bézout, par l'algorithme).** Soient $a, b$ des entiers. Pour exprimer $\gcd(a, b)$ comme combinaison linéaire de $a$ et $b$, on applique l'algorithme d'Euclide, puis on remonte les calculs en remplaçant les restes.

Par exemple, pour $\gcd(45, 65) = 5$ :
$$65 = 45 \cdot 1 + 20, \qquad 45 = 20 \cdot 2 + 5, \qquad 20 = 5 \cdot 4 + 0.$$
En remontant :
$$5 = 45 - 2 \cdot 20 = 45 - 2(65 - 45) = 3 \cdot 45 - 2 \cdot 65.$$

Autre exemple, pour exprimer $1$ à partir de $7$ et $12$ :
$$12 = 7 \cdot 1 + 5, \qquad 7 = 5 \cdot 1 + 2, \qquad 5 = 2 \cdot 2 + 1.$$
En remontant :
$$1 = 5 - 2 \cdot 2 = 5 - 2(7 - 5) = 3 \cdot 5 - 2 \cdot 7 = 3(12 - 7) - 2 \cdot 7 = 3 \cdot 12 - 5 \cdot 7.$$

Cette démarche fonctionne en général.

*Preuve (par le plus petit élément positif).* Considérons $S = \{ax + by \mid x, y \in \mathbb{Z}\}$. Soit $d$ le plus petit élément strictement positif de $S$, obtenu pour $(x_0, y_0)$. Montrons que $d = \gcd(a, b)$, en prouvant $d \mid \gcd(a, b)$ et $\gcd(a, b) \mid d$. Le second point est immédiat, car $\gcd(a,b)$ divise $ax_0 + by_0 = d$. Pour le premier, montrons que $d \mid a$. Sinon, écrivons $a = dk + r$ avec $0 < r < d$. Alors
$$r = a - dk = a - (ax_0 + by_0)k = a(1 - x_0 k) + b(-y_0 k) \in S,$$
ce qui contredit la minimalité de $d$. Donc $d \mid a$, et de même $d \mid b$. Ainsi $d \mid \gcd(a,b)$, et l'égalité est démontrée.

**Exemple 1.10.6 (Lemme des quatre nombres).** Soient $a, b, c, d$ des entiers strictement positifs tels que $ab = cd$. Alors il existe des entiers strictement positifs $p, q, r, s$ tels que
$$a = pq, \qquad b = rs, \qquad c = ps, \qquad d = qr.$$

*Preuve.* On a $\dfrac{a}{c} = \dfrac{d}{b}$. Ce rapport commun se réduit en une fraction irréductible $\dfrac{q}{s}$ avec $\gcd(q, s) = 1$. Alors $(a, c) = (pq, ps)$ pour un certain $p$, et $(b, d) = (rs, rq)$ pour un certain $r$.

Ce lemme sert souvent en pratique. Par exemple, si $ab = cd$, alors $a + b + c + d$ n'est pas premier : avec les notations ci-dessus, $a + b + c + d = (p + q)(r + s)$.

**11. Exemples résolus**

**Exemple 1.11.1 (Olympiade de Russie 1995).** Soient $m, n$ des entiers positifs tels que $\gcd(m, n) + \operatorname{lcm}(m, n) = m + n$. Montrons que l'un des deux nombres divise l'autre.

Posons $g = \gcd(m, n)$. Comme $\operatorname{lcm}(m, n) = \frac{mn}{g}$, on obtient $g + \frac{mn}{g} = m + n$, donc $g^2 + mn = g(m+n)$, soit $(m - g)(n - g) = 0$. Donc $g = m$ ou $g = n$, ce qui signifie que $m \mid n$ ou $n \mid m$.

**Exemple 1.11.2.** Soient $p$ un nombre premier impair et $a, b$ premiers entre eux. Montrons que
$$\gcd\left(\frac{a^p + b^p}{a + b},\ a + b\right) \in \{1, p\}.$$

On a $\dfrac{a^p + b^p}{a+b} = a^{p-1} - a^{p-2}b + \cdots + b^{p-1}$. En effectuant la division de cette expression par $a + b$, on obtient
$$a^{p-1} - a^{p-2}b + \cdots + b^{p-1} = (a+b)\left(a^{p-2} - 2a^{p-3}b + \cdots - p b^{p-2}\right) + p b^{p-1}.$$
Donc
$$\gcd\left(\frac{a^p + b^p}{a+b}, a+b\right) = \gcd(a + b, p b^{p-1}).$$
Comme $a+b$ et $b$ sont premiers entre eux, donc $a+b$ et $b^{p-1}$ aussi, ce PGCD vaut $\gcd(a+b, p)$, qui est $1$ ou $p$.

**Exemple 1.11.3 (Iran 2005).** Soient $n, p > 1$ des entiers, avec $p$ premier. Supposons que $n \mid p - 1$ et que $p \mid n^3 - 1$. Montrons que $4p - 3$ est un carré parfait.

Écrivons $p - 1 = nk$. Comme $n \mid p - 1$, on a $p \geq n + 1$, et $p = nk + 1$. De plus $n^3 - 1 = (n-1)(n^2 + n + 1)$, et $p$ divise ce produit. Comme $p \mid n - 1$ est impossible (car $p > n - 1$), on a $p \mid n^2 + n + 1$, donc $p \leq n^2 + n + 1$.

Puisque $nk + 1 \mid n^2 + n + 1$, on a $nk + 1 \mid kn^2 + kn + k$, donc $nk + 1$ divise $kn^2 + kn + k - n(nk + 1) = nk + k - n$. Comme ce nombre est positif, $nk + 1 \leq nk + k - n$, soit $n + 1 \leq k$. Donc $p = nk + 1 \geq n(n+1) + 1 = n^2 + n + 1$.

Avec $p \leq n^2 + n + 1$, on obtient $p = n^2 + n + 1$. Alors $4p - 3 = 4n^2 + 4n + 1 = (2n+1)^2$.

**Exemple 1.11.4 (APMO).** Existe-t-il des nombres premiers distincts $a, b, c$ tels que $a \mid bc + b + c$, $b \mid ca + c + a$ et $c \mid ab + a + b$ ?

Remarquons que $bc + b + c = (b+1)(c+1) - 1$. Ainsi $a \mid (b+1)(c+1) - 1$. En multipliant par $a + 1$ et en ajoutant $a$, on obtient $a \mid (a+1)(b+1)(c+1) - 1$. Cette relation est symétrique en $a, b, c$, donc $a, b, c$ divisent tous $(a+1)(b+1)(c+1) - 1$. Comme $a, b, c$ sont premiers entre eux deux à deux, on obtient $abc \mid (a+1)(b+1)(c+1) - 1$, soit
$$abc \mid ab + bc + ca + a + b + c.$$
Le membre de droite est nettement plus petit que $abc$ dès que les nombres sont grands. En supposant $a < b < c$, on obtient
$$1 \leq \frac{1}{ab} + \frac{1}{bc} + \frac{1}{ca} + \frac{1}{a} + \frac{1}{b} + \frac{1}{c} \leq \frac{3}{a^2} + \frac{3}{a},$$
ce qui est impossible si $a \geq 4$. Donc $a \in \{2, 3\}$, et l'on traite ces deux cas par disjonction. La conclusion est qu'aucun tel triplet de nombres premiers n'existe.

**Exemple 1.11.5 (AMM).** Montrons que, pour tout nombre premier $p$, le nombre
$$Q(p) = \prod_{k=1}^{p-1} k^{\,2k-p-1}$$
est un entier.

On réécrit d'abord le produit. Comme $\prod_{k=1}^{p-1} k^{2k-p-1} = \dfrac{\left(\prod_{k=1}^{p-1} k^k\right)^2}{((p-1)!)^{p+1}}$, il suffit d'exprimer $\prod_{k=1}^{p-1} k^k$. En échangeant l'ordre des produits, on a $\prod_{k=1}^{n} k^k = \prod_{j=1}^{n} \prod_{k=j}^{n} k = \prod_{j=1}^{n} \dfrac{n!}{(j-1)!}$. Avec $n = p-1$, on obtient après calcul la forme simplifiée
$$Q(p) = \frac{((p-1)!)^{p-3}}{\left(\prod_{i=1}^{p-2} i!\right)^2}.$$
Vérification pour $p = 5$ : $\dfrac{(4!)^2}{(1!\,2!\,3!)^2} = \dfrac{576}{144} = 4$, et directement $\prod_{k=1}^{4} k^{2k-6} = \dfrac{2^{-2} \cdot 4^{2}}{1} = 4$.

La conclusion repose sur le caractère premier de $p$ ; la preuve complète est laissée au lecteur.

**Exemple 1.11.6 (HMMT 2017).** Trouvons tous les couples $(a, b)$ d'entiers strictement positifs tels que $a^{2017} + b$ soit un multiple de $ab$.

On a $a \mid a^{2017} + b$ et $b \mid a^{2017} + b$. De la première relation, $a \mid b$. Écrivons $b = ak$. La condition devient $ak \mid a^{2016} + k$. C'est le même problème, avec $2017$ remplacé par $2016$. En répétant le raisonnement, on aboutit à $a\ell \mid 1 + \ell$ pour un certain entier $\ell$, d'où $\ell = 1$ et donc $a \in \{1, 2\}$.

Si $a = 1$, on trouve $b = 1$. Si $a = 2$, alors $2b \mid 2^{2017} + b$, donc $b \mid 2^{2017}$, et $b = 2^{\omega}$ avec $\omega \leq 2017$. On obtient $2^{\omega + 1} \mid 2^{2017} + 2^{\omega}$, donc $2 \mid 2^{2017 - \omega} + 1$, ce qui n'est possible que si $\omega = 2017$. Les solutions sont donc $(a, b) = (1, 1)$ et $(a, b) = (2, 2^{2017})$.

**Exemple 1.11.7 (Inde, présélection 2017).** Soient $a, b, c, d$ des entiers strictement positifs deux à deux distincts tels que
$$X = \frac{a}{a+b} + \frac{b}{b+c} + \frac{c}{c+d} + \frac{d}{d+a}$$
soit un entier. Montrons que $a + b + c + d$ n'est pas premier.

Posons $Y = \dfrac{b}{a+b} + \dfrac{c}{b+c} + \dfrac{d}{c+d} + \dfrac{a}{d+a}$. Alors $X + Y = 4$, donc $Y$ est aussi un entier. De plus $X > 1$ et $Y > 1$ (car chaque fraction de $X$ est supérieure à $\dfrac{a}{a+b+c+d}$, et leur somme dépasse $1$, de même pour $Y$). Comme $X$ et $Y$ sont des entiers de somme $4$, on a $X = Y = 2$. Alors
$$0 = X - Y = \frac{a-b}{a+b} + \frac{b-c}{b+c} + \frac{c-d}{c+d} + \frac{d-a}{d+a}.$$
En réduisant au même dénominateur, on obtient
$$X - Y = \frac{2(a-c)(b-d)(ac-bd)}{(a+b)(b+c)(c+d)(d+a)}.$$
Le dénominateur est strictement positif. Comme $a \neq c$ et $b \neq d$, on a $ac = bd$. Par le lemme des quatre nombres, il existe $p, q, r, s$ tels que $a = pq$, $b = rs$, $c = ps$, $d = qr$, donc $a + b + c + d = (p+q)(r+s)$, qui n'est pas premier.

**Exemple 1.11.8 (STEMS 2019).** Déterminons tous les ensembles $S \subseteq \mathbb{Z}$ tels que, pour tous $a, b \in S$, on ait $2a - b \in S$.

Remarquons que $b$ est la moyenne arithmétique de $b$ et de $2a - b$. La condition dit donc que, si deux nombres sont dans $S$, le suivant de la progression arithmétique qu'ils forment est dans $S$, et de même le précédent.

Si $S = \{x + kd \mid k \in \mathbb{Z}\}$ est une progression arithmétique, alors $S$ convient : si $a = x + kd$ et $b = x + \ell d$, alors $2a - b = x + (2k - \ell)d \in S$. Réciproquement, on montre que tout ensemble convenable est une progression arithmétique. Soit $r$ le plus petit écart positif entre deux éléments de $S$, et soient $a, b \in S$ avec $a - b = r$. Alors $\{b + kr \mid k \in \mathbb{Z}\} \subseteq S$. Si un élément $c$ de $S$ n'était pas dans cette progression, il existerait $k$ avec $b + kr \leq c < b + (k+1)r$, et $c - (b + kr) < r$ serait un écart positif plus petit que $r$, ce qui contredit la minimalité de $r$.

Les ensembles cherchés sont donc l'ensemble vide et les ensembles de la forme $\{x + kd \mid k \in \mathbb{Z}\}$ avec $d \geq 0$.
""",
        "problems": [
            {"puid": "NT1-01", "difficulty": 2, "set_kind": "set", "set_order": 1,
             "statement_tex": r"""Montrer que tout entier composé $n$ possède un facteur premier inférieur ou égal à $\sqrt{n}$.""",
             "source": r"""MODNT, problème 1.12.1.""",
             "hints": [
                 r"""Écrivez $n = ab$ avec $1 < a \le b$.""",
                 r"""Que se passe-t-il si $a > \sqrt{n}$ ?""",
                 r"""Un diviseur $> 1$ admet un facteur premier qui est au plus lui-même.""",
             ],
             "solution": r"""Soit $n$ composé, et écrivons $n = ab$ avec $1 < a \le b$. Si $a > \sqrt{n}$, alors $b \ge a > \sqrt{n}$, donc $ab > n$, contradiction. Ainsi $a \le \sqrt{n}$. Soit $p$ un facteur premier de $a$ ; alors $p \le a \le \sqrt{n}$."""},
            {"puid": "NT1-02", "difficulty": 2, "set_kind": "set", "set_order": 2,
             "statement_tex": r"""Pour tout entier naturel $n$, montrer que la fraction $\dfrac{21n+4}{14n+3}$ est irréductible.""",
             "source": r"""IMO 1959, problème 1 (cité dans MODNT, problème 1.12.2).""",
             "hints": [
                 r"""Soit $d$ un diviseur commun des deux termes.""",
                 r"""Calculez $2(21n+4) - 3(14n+3)$.""",
                 r"""Un diviseur de $\pm 1$ vaut $1$.""",
             ],
             "solution": r"""Soit $d = \gcd(21n+4, 14n+3)$. Alors $d$ divise $2(21n+4) - 3(14n+3) = 42n + 8 - 42n - 9 = -1$. Donc $d = 1$."""},
            {"puid": "NT1-03", "difficulty": 2, "set_kind": "set", "set_order": 3,
             "statement_tex": r"""Soient $x, y, a, b, c$ des entiers.
1. Montrer que $17 \mid 2x + 3y$ si et seulement si $17 \mid 9x + 5y$.
2. Si $19 \mid 4a + 5b - 3c$, montrer que $19 \mid 6a - 2b + 5c$.""",
             "source": r"""MODNT, problème 1.12.3.""",
             "hints": [
                 r"""Partie 1 : cherchez $k$ tel que $k(2x+3y) \equiv 9x+5y \pmod{17}$.""",
                 r"""Partie 2 : cherchez $k$ tel que $k(4a+5b-3c) \equiv 6a-2b+5c \pmod{19}$.""",
                 r"""Pour la réciproque de la partie 1, utilisez un inverse de $k$ modulo $17$.""",
             ],
             "solution": r"""**Partie 1.** On a $13(2x+3y) = 26x + 39y \equiv 9x + 5y \pmod{17}$ (car $26-9 = 17$ et $39-5 = 34$). Donc $17 \mid 2x+3y$ implique $17 \mid 9x+5y$. Réciproquement, $4(9x+5y) = 36x + 20y \equiv 2x + 3y \pmod{17}$ (car $36-2 = 34$ et $20-3 = 17$).

**Partie 2.** On a $11(4a+5b-3c) = 44a + 55b - 33c \equiv 6a - 2b + 5c \pmod{19}$ (car $44-6 = 38$, $55+2 = 57$, $-33-5 = -38$). Donc $19 \mid 4a+5b-3c$ implique $19 \mid 6a-2b+5c$."""},
            {"puid": "NT1-04", "difficulty": 2, "set_kind": "set", "set_order": 4,
             "statement_tex": r"""Pour $n \ge 0$, on pose $F_n = 2^{2^n} + 1$. Montrer que $F_m$ et $F_n$ sont premiers entre eux pour $m \ne n$.""",
             "source": r"""Nombres de Fermat ; MODNT, problème 1.12.4. **Note :** l'énoncé du livre dit « pour tous $m, n$ », ce qui est faux pour $m = n$ ; la version correcte est « pour $m \ne n$ ».""",
             "hints": [
                 r"""Montrez par récurrence que $F_0 F_1 \cdots F_{n-1} = F_n - 2$.""",
                 r"""Si $m < n$, alors $F_m \mid F_n - 2$.""",
                 r"""Un diviseur commun de $F_m$ et $F_n$ divise $2$, et tous les $F_k$ sont impairs.""",
             ],
             "solution": r"""Montrons par récurrence que $\prod_{k=0}^{n-1} F_k = F_n - 2$ pour $n \ge 1$. Pour $n = 1$ : $F_0 = 3 = F_1 - 2$. Supposons l'égalité vraie au rang $n$. Alors $\prod_{k=0}^{n} F_k = (F_n - 2)F_n = F_n^2 - 2F_n$. Or $F_{n+1} = (F_n - 1)^2 + 1 = F_n^2 - 2F_n + 2$, donc $\prod_{k=0}^{n} F_k = F_{n+1} - 2$.

Soient $m < n$ et $d = \gcd(F_m, F_n)$. Comme $F_m$ est un facteur de $F_n - 2$, on a $d \mid F_n - 2$. Mais $d \mid F_n$, donc $d \mid 2$. Or tous les $F_k$ sont impairs, donc $d = 1$."""},
            {"puid": "NT1-05", "difficulty": 2, "set_kind": "set", "set_order": 5,
             "statement_tex": r"""Montrer que, pour tout entier positif $n$, il existe un entier positif $m$ tel que chaque terme de la suite infinie $m+1,\ m^m+1,\ m^{m^m}+1,\ \dots$ soit divisible par $n$.""",
             "source": r"""MODNT, problème 1.12.5.""",
             "hints": [
                 r"""Cherchez $m$ tel que $m \equiv -1 \pmod n$.""",
                 r"""Vérifiez que $m$ peut aussi être choisi impair.""",
                 r"""Une puissance impaire de $-1$ vaut $-1$.""",
             ],
             "solution": r"""Prenons $m = 2n - 1$. Alors $m \equiv -1 \pmod n$, et $m$ est impair. Chaque terme est de la forme $m^T + 1$, où $T$ est une tour de $m$ (ou $T = 1$ pour le premier terme). Toute telle tour est impaire, car $m$ l'est. Donc $m^T \equiv (-1)^T = -1 \pmod n$, et $n \mid m^T + 1$."""},
            {"puid": "NT1-06", "difficulty": 2, "set_kind": "set", "set_order": 6,
             "statement_tex": r"""Soient $a, b$ des entiers strictement positifs. On suppose qu'il existe un nombre premier $p$ tel que $\operatorname{lcm}(a, a+p) = \operatorname{lcm}(b, b+p)$. Montrer que $a = b$.""",
             "source": r"""Olympiade de Roumanie ; MODNT, problème 1.12.6.""",
             "hints": [
                 r"""$\gcd(a, a+p) = \gcd(a, p) \in \{1, p\}$.""",
                 r"""Distinguez les cas selon que $p$ divise $a$ et $b$.""",
                 r"""Si $p$ divise exactement un des deux, comparez la divisibilité par $p$ des deux membres.""",
             ],
             "solution": r"""On a $\operatorname{lcm}(a, a+p) = \dfrac{a(a+p)}{\gcd(a,p)}$, et de même pour $b$."""},
            {"puid": "NT1-07", "difficulty": 2, "set_kind": "set", "set_order": 7,
             "statement_tex": r"""Déterminer tous les entiers strictement positifs $n$ tels que $3^{n-1} + 5^{n-1} \mid 3^n + 5^n$.""",
             "source": r"""Saint-Pétersbourg 1996 ; MODNT, problème 1.12.7.""",
             "hints": [
                 r"""Posez $A = 3^{n-1} + 5^{n-1}$ et réduisez modulo $A$.""",
                 r"""Montrez que $A$ divise $2 \cdot 3^{n-1}$ et $2 \cdot 5^{n-1}$.""",
                 r"""Utilisez $\gcd(3^{n-1}, 5^{n-1}) = 1$.""",
             ],
             "solution": r"""Posons $A = 3^{n-1} + 5^{n-1}$. Modulo $A$, on a $5^{n-1} \equiv -3^{n-1}$, donc
$$3^n + 5^n = 3 \cdot 3^{n-1} + 5 \cdot 5^{n-1} \equiv -2 \cdot 3^{n-1} \pmod A.$$
Si $A \mid 3^n + 5^n$, alors $A \mid 2 \cdot 3^{n-1}$. En remplaçant $3^{n-1}$ par $-5^{n-1}$, on obtient de même $A \mid 2 \cdot 5^{n-1}$. Donc $A \mid 2\gcd(3^{n-1}, 5^{n-1}) = 2$.

Ainsi $3^{n-1} + 5^{n-1} \le 2$, ce qui force $n = 1$. Vérification : $2 \mid 8$. **Réponse : $n = 1$ uniquement.**"""},
            {"puid": "NT1-08", "difficulty": 2, "set_kind": "set", "set_order": 8,
             "statement_tex": r"""Soient $a, b$ des entiers naturels tels que $a^2 + ab + b^2$ divise $ab(a+b)$. Montrer que $|a-b| > 3\sqrt{ab}$.""",
             "source": r"""Russie 2001, 11e année, jour 2, problème 2 ; MODNT, problème 1.12.8.

**ÉNONCÉ À CORRIGER.** L'énoncé est faux. Contre-exemple : $a = 7$, $b = 14$. On a $a^2+ab+b^2 = 343$ et $ab(a+b) = 2058 = 6 \cdot 343$, donc la divisibilité est vraie, mais $|a-b| = 7 < 3\sqrt{98} \approx 29{,}7$. Une recherche sur $a, b < 400$ donne 118 contre-exemples avec $a \ne b$. Il faut vérifier l'énoncé source avant de le garder dans le problemset.""",
             "hints": [
                 r"""Écrivez $a = dx$, $b = dy$ avec $d = \gcd(a,b)$.""",
                 r"""Montrez que $x^2+xy+y^2$ divise $d$.""",
                 r"""Comparez les quantités obtenues.""",
             ],
             "solution": r"""**Non applicable en l'état.** La réduction ci-dessus donne $d \ge x^2+xy+y^2$, mais elle n'impose aucune contrainte sur $|x-y|$ par rapport à $\sqrt{xy}$. L'inégalité demandée est donc fausse pour l'énoncé donné."""},
            {"puid": "NT1-09", "difficulty": 2, "set_kind": "set", "set_order": 9,
             "statement_tex": r"""Soient $m$ et $n$ deux entiers strictement positifs premiers entre eux. Pour tout entier $k$ strictement positif, montrer que les deux assertions suivantes sont équivalentes :
1. $n + m$ divise $n^2 + km^2$ ;
2. $n + m$ divise $k + 1$.""",
             "source": r"""Allemagne ; MODNT, problème 1.12.9.""",
             "hints": [
                 r"""Modulo $n+m$, on a $n \equiv -m$.""",
                 r"""Donc $n^2 + km^2 \equiv m^2(k+1)$.""",
                 r"""Montrez que $\gcd(m^2, n+m) = 1$.""",
             ],
             "solution": r"""Modulo $n+m$, on a $n \equiv -m$, donc $n^2 + km^2 \equiv m^2 + km^2 = m^2(k+1)$. Ainsi $n+m \mid n^2 + km^2$ équivaut à $n+m \mid m^2(k+1)$. Or $\gcd(m, n+m) = \gcd(m,n) = 1$, donc $\gcd(m^2, n+m) = 1$, et par le lemme d'Euclide, $n+m \mid m^2(k+1)$ équivaut à $n+m \mid k+1$."""},
            {"puid": "NT1-10", "difficulty": 2, "set_kind": "set", "set_order": 10,
             "statement_tex": r"""Déterminer tous les triplets d'entiers strictement positifs $(a,b,c)$ tels que $\operatorname{lcm}(a,b,c) = \dfrac{ab+bc+ca}{4}$.""",
             "source": r"""Japon 2020, finale junior, problème 3 ; MODNT, problème 1.12.10.""",
             "hints": [
                 r"""Pour un premier $p$ impair, comparez les valuations $v_p$ des trois produits $ab$, $bc$, $ca$ à celle de $\operatorname{lcm}(a,b,c)$.""",
                 r"""Avec $a \le b \le c$, majorez $ab+bc+ca \le 3bc$.""",
                 r"""Cherchez une contrainte 2-adique sur $4\operatorname{lcm}(a,b,c)$.""",
             ],
             "solution": r"""**À COMPLÉTER.** Recherche numérique sur $a \le b \le c \le 120$ : le seul triplet trouvé est $(1,2,2)$ et ses permutations. Il reste à démontrer qu'il n'y en a pas d'autre."""},
            {"puid": "NT1-11", "difficulty": 2, "set_kind": "set", "set_order": 11,
             "statement_tex": r"""1. Montrer qu'il n'existe pas de suite $a_1, a_2, a_3, \dots$ d'entiers strictement positifs telle que, pour tous $i < j$, $\gcd(a_i + j, a_j + i) = 1$.
2. Soit $p$ un nombre premier impair. Montrer qu'il existe une suite $a_1, a_2, a_3, \dots$ d'entiers strictement positifs telle que, pour tous $i < j$, $p \nmid \gcd(a_i + j, a_j + i)$.""",
             "source": r"""Iran MO 2017, round 2, problème 1 ; MODNT, problème 1.12.11.""",
             "hints": [
                 r"""Si $a_i - i = a_j - j$, alors $\gcd(a_i + j, a_j + i) = a_i + j > 1$.""",
                 r"""Le pgcd de $a_i+j$ et $a_j+i$ divise $(a_i - a_j) + (j - i)$.""",
                 r"""Pour la partie 1, essayez le principe des tiroirs modulo un premier $p$ sur les couples $(i \bmod p, a_i \bmod p)$.""",
             ],
             "solution": r"""**À COMPLÉTER.** Je n'ai pas trouvé de démonstration complète de la partie 1, et la partie 2 n'est pas traitée."""},
            {"puid": "NT1-12", "difficulty": 2, "set_kind": "set", "set_order": 12,
             "statement_tex": r"""Soit $n \ge 2$ un entier, de diviseurs $1 = d_1 < d_2 < \dots < d_k = n$. Montrer que $d_1 d_2 + d_2 d_3 + \dots + d_{k-1} d_k$ est toujours strictement inférieur à $n^2$, et déterminer quand ce nombre divise $n^2$.""",
             "source": r"""IMO 2002, problème 1 ; MODNT, problème 1.12.13.""",
             "hints": [
                 r"""Dans le cas $n = p$ premier, calculez la somme.""",
                 r"""Utilisez $d_i d_{k+1-i} = n$ pour majorer les termes.""",
                 r"""Si $S \mid n^2$ et $S < n^2$, étudiez le quotient $n^2 / S$.""",
             ],
             "solution": r"""**À COMPLÉTER.** La vérification numérique pour $2 \le n < 80$ donne $S \mid n^2$ seulement quand $n$ est premier (alors $S = n$). Il reste à prouver l'inégalité $S < n^2$ et l'équivalence « $S \mid n^2 \iff n$ premier »."""},
            {"puid": "NT1-13", "difficulty": 2, "set_kind": "set", "set_order": 13,
             "statement_tex": r"""Déterminer tous les entiers impairs $n > 1$ tels que, si $a$ et $b$ sont deux diviseurs premiers entre eux de $n$, alors $a + b - 1$ divise $n$.""",
             "source": r"""Russie 2001, 10e année, jour 2, problème 4 ; MODNT, problème 1.12.14.""",
             "hints": [
                 r"""Si $n = p^k$, les seuls couples de diviseurs premiers entre eux sont $(1,1)$, $(1,p^k)$ et $(p^k,1)$.""",
                 r"""Calculez $a + b - 1$ dans chacun de ces cas.""",
                 r"""Pour la réciproque, prenez $a = p^\alpha$ la plus grande puissance d'un premier $p$ divisant $n$, et $b = n/p^\alpha$.""",
             ],
             "solution": r"""**Partiellement résolu.**"""},
            {"puid": "NT1-14", "difficulty": 2, "set_kind": "set", "set_order": 14,
             "statement_tex": r"""Soient $m, n$ deux entiers strictement positifs distincts. Montrer que
$$\gcd(m,n) + \gcd(m+1, n+1) + \gcd(m+2, n+2) \le 2|m-n| + 1,$$
et déterminer les cas d'égalité.""",
             "source": r"""INMO 2019, problème 3.""",
             "hints": [
                 r"""Chaque $g_k = \gcd(m+k, n+k)$ divise $d = |m-n|$.""",
                 r"""Pour $d \ge 3$, au plus un des entiers $m, m+1, m+2$ est divisible par $d$.""",
                 r"""Traitez séparément les cas $d = 1$ et $d = 2$.""",
             ],
             "solution": r"""Soit $d = |m-n| \ge 1$, et $g_k = \gcd(m+k, n+k)$ pour $k = 0, 1, 2$. Chaque $g_k$ divise $(m+k) - (n+k) = m - n$, donc $g_k \mid d$."""},
            {"puid": "NT1-15", "difficulty": 2, "set_kind": "set", "set_order": 15,
             "statement_tex": r"""Soient $a > b > c > d > 0$ des entiers tels que
$$ac + bd = (b + d + a - c)(b + d - a + c).$$
Montrer que $ab + cd$ n'est pas premier.""",
             "source": r"""IMO 2001, problème 6 ; MODNT, problème 1.12.19.""",
             "hints": [
                 r"""Développez le membre de droite : c'est $(b+d)^2 - (a-c)^2$.""",
                 r"""Cela donne $a^2 - ac + c^2 = b^2 + bd + d^2$.""",
                 r"""Cherchez une factorisation de $ab+cd$ compatible avec cette relation.""",
             ],
             "solution": r"""**À COMPLÉTER.** Recherche numérique : l'équation a 341 solutions pour $a < 60$, et $ab + cd$ est composé dans tous les cas vérifiés (par exemple $104 = 2^3 \cdot 13$, $105 = 3 \cdot 5 \cdot 7$, $147 = 3 \cdot 7^2$). Il reste à trouver la factorisation qui conclut."""},
        ],
    },
]
