# Quantiles, effectifs et allocation

On note Y=1 un accident avec au moins un usager enregistré tué dans les trente jours. L'analyse est conditionnelle à l'enregistrement d'un accident corporel et à une étiquette déterminable. G désigne le département ; les probabilités du prédicteur sont fixées avant calibration conforme.

## Couverture par cellule

Le score est s(x,y)=1−p̂(y|x). Pour m scores de calibration dans une cellule (g,y), ordonnés s_(1)≤…≤s_(m), on pose

\[
k=\lceil(m+1)(1-\alpha)\rceil,\qquad
q_{g,y}=\begin{cases}s_{(k)}&k\le m,\\+\infty&k=m+1.\end{cases}
\]

L'ensemble est C(x,g)={y : s(x,y)≤q_(g,y)}. La référence pooled utilise tous les scores ; classwise utilise seulement y ; la méthode locale utilise (g,y). Les égalités au seuil sont incluses, ce qui peut rendre la couverture conservatrice.

**Garantie conditionnelle.** Si les scores de calibration et celui d'un nouvel accident sont échangeables dans chaque cellule, conditionnellement au modèle, aux catégories et au mécanisme d'allocation indépendant, le rang du nouveau score est uniforme en l'absence d'ex æquo. Ainsi P{Y∈C(X,G)|G=g,Y=y}≥1−α, en moyennant sur la calibration et le nouvel accident. Cela n'affirme pas que chaque calibration réalisée atteint exactement ce niveau. Avec un score continu et k≤m, la probabilité vaut k/(m+1), comprise entre 1−α et 1−α+1/(m+1). Les ex æquo peuvent accroître la couverture.

Le seuil est fini seulement si m≥ceil(1/α)−1 : **9 observations de la classe dans la cellule à α=0,10 ; 19 à α=0,05**. Ce minimum ne garantit aucune précision utile du quantile. Si m=0 ou m est insuffisant, la classe est toujours incluse ; aucune substitution par un seuil pooled n'est effectuée. En classification binaire, toujours retourner {0,1} couvre tout mais ne discrimine rien.

Sous scores i.i.d. continus de fonction F, F(s_(k)) suit Beta(k,m+1−k). La variance du niveau de couverture réalisé vaut k(m+1−k)/[(m+1)²(m+2)]. Pour un niveau intérieur et m grand, elle est de l'ordre α(1−α)/m. Cette approximation décrit une incertitude de rang, pas la variance de la valeur du quantile lorsque sa densité est faible.

## Budget et rareté

Soit n_g le nombre d'étiquettes achetées dans g et p_g la probabilité qu'une acquisition fournisse un décès connu. Dans une approximation binomiale, M_(g,1)~Bin(n_g,p_g), donc

\[
P(q_{g,1}=+\infty)=P(M_{g,1}<\lceil1/\alpha\rceil-1)
=\sum_{j=0}^{m_{\min}-1}{n_g\choose j}p_g^j(1-p_g)^{n_g-j}.
\]

Pour un pool fini fixé, l'expression exacte est hypergéométrique. La règle n_g p_g≥m_min ne contrôle pas la probabilité d'une cellule insuffisante ; elle ne porte que sur l'espérance. Des labels indéterminés consomment du budget et ne sont jamais transformés en non-décès.

Une approximation de la somme des variances des niveaux de quantile fatal, avec importance régionale w_g, conduit au critère

\[
J(n)=\sum_g\frac{w_g}{n_g p_g},\quad \sum_g n_g=B_{\rm cal}.
\]

La dérivée de Lagrange donne n_g proportionnel à sqrt(w_g/p_g). Cette étude fixe w_g=1 : le critère donne la même importance aux régions, contrairement à un objectif pondéré par leur population. Il remplace E[1/M] par 1/E[M], néglige la masse en zéro, la densité des scores et les corrections de population finie. **C'est un critère substitutif, pas un théorème d'optimalité de la couverture ou de la taille des ensembles.**

Pour a_g=w_g/p̂_g, l'allocation entière minimise exactement somme a_g/n_g, sous 1≤n_g≤capacité_g pour les régions non vides, par incréments de gain a_g/[n_g(n_g+1)]. Les gains décroissent ; échanger une unité choisie avec une unité de gain inférieur ne peut améliorer la somme. Choisir successivement les gains maximaux donne donc l'optimum discret sous ces bornes. Si le budget ne permet pas une unité par région, cette optimalité ne s'applique plus au critère fini ; nos budgets réels satisfont cette condition après pilot.

## Pourquoi séparer le pilot

Dans chaque département présent, on tire d'abord au plus cinq accidents sans remise. Le coût B_pilot est déduit de B. Ces observations sont exclues de la calibration conforme. On estime p̂_g=(d_g+20 p_source)/(r_g+20), tronqué dans [0,005 ; 0,5], où d_g compte les décès observés et r_g tous les labels pilot acquis, y compris indéterminés. Le taux source est calculé sur les étiquettes historiques déterminées des régions sources, sans information sur les régions laissées de côté. Ce lissage est une hypothèse pratique, pas une estimation garantie transportable.

Conditionnellement au pilot, les quotas sont fixés avant de révéler les autres labels. Le tirage suivant est uniforme à l'intérieur de chaque département. Sous une génération i.i.d. intrarégionale, les observations restantes et le test gardent la même loi intrarégionale ; sélectionner ensuite par classe conserve l'échangeabilité dans chaque cellule. Les quotas peuvent donc dépendre du pilot sans invalider la garantie précédente. Réutiliser le pilot dans les quantiles après avoir choisi les quotas à partir de ses labels compromettrait cet argument. Choisir directement les cas supposés mortels par le score changerait également la loi des scores et demanderait une correction spécifique.

Les références uniforme et proportionnelle utilisent tout B pour calibrer, sans pilot. La comparaison porte sur le coût total réel ; elle inclut donc le désavantage potentiel du pilot de la règle candidate. Les effectifs et les coûts sont publiés pour chaque essai.

## Décalages et limites des garanties

- Les calibrations sources pooled et classwise demanderaient l'échangeabilité source–cible, globale ou par classe. Elle n'est pas présumée dans BAAC.
- Le quantile pondéré demande un rapport de densités correct, le recouvrement des supports et la stabilité de P(Y|X). Son atome du point test est à +∞. L'estimation par régression de domaine et la troncature des poids rendent ce bras exploratoire.
- La calibration locale exige la stabilité de la distribution entre pool d'adaptation et test dans chaque cellule. Une séparation aléatoire au sein de 2025 représente une adaptation rétrospective sur la même année ; elle n'est pas une preuve de validité pour un déploiement futur en 2026.
- Les accidents voisins ou associés à une même situation météorologique peuvent dépendre les uns des autres. Le bootstrap par département décrit une sensibilité spatiale ; il ne restaure pas une garantie conforme ni l'indépendance entre départements.
- L'exclusion des étiquettes indéterminées change la population estimée. Aucune garantie n'est affirmée pour les accidents dont l'état vital reste inconnu ou pour les personnes non enregistrées.

Les simulations séparent ces hypothèses : échangeabilité locale, décalage source–cible, rupture entre calibration et test, et effets départementaux corrélés. Elles vérifient des mécanismes connus ; les observations BAAC restent une validation empirique sous hypothèses non démontrées.
