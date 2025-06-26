# Regel 7-1 Beregning av faktor pi
1 Faktor pi for en avdeling eller gruppe med avdelinger skal beregnes i henhold til nr. 1.1 og 1.2 ved hjelp av følgende betegnelser:
j = det akterste skadesonenummeret involvert i skaden, der nr. 1 starter ved akterstevnen
n = antallet tilstøtende skadesoner involvert i skaden
k = nummeret til et bestemt langskipsskott som barriere for tverrskipspenetrering i en skadesone talt fra huden mot senterlinjen. Huden har k = 0
x1 = avstanden fra aktre endepunkt av Ls til den aktre enden av den aktuelle sonen
x2 = avstanden fra aktre endepunkt av Ls til den fremre enden av den aktuelle sonen,
b = midlere tverrskips avstand i meter målt i rette vinkler på senterlinjen ved største oppdelingsdypgående mellom huden og et tenkt vertikalt plan som strekker seg mellom langskipsavgrensningene brukt i beregningen av faktoren pi, og som er en tangent til, eller felles med, hele eller deler av det ytterste punktet av langskipsskottet som betraktes. Dette vertikale planet skal orienteres slik at den midlere tverrskips avstanden til huden er et maksimum, men ikke mer enn to ganger den minste avstanden mellom planet og huden. Når den øvre delen av et langskipsskott er under største oppdelingsdypgående, antas det vertikale planet brukt for bestemmelse av b å strekke seg oppover mot dypeste oppdelingsvannlinje. b skal ikke i noen tilfeller være større enn B/2.
Når skaden kun involverer en enkelt sone:
$$p_i = p(x1_j, x2_j) \cdot [r(x1_j, x2_j, b_k) - r(x1_j, x2_j, b_{k-1})]$$
Når skaden involverer to tilstøtende soner:
$$\begin{align} p_i = p(x1_j, x2_{j+1}) &\cdot [r(x1_j, x2_{j+1}, b_k) - r(x1_j, x2_{j+1}, b_{k-1})] - p(x1_j, x2_j) \\ &\cdot [r(x1_j, x2_j, b_k) - r(x1_j, x2_j, b_{k-1})] - p(x1_{j+1}, x2_{j+1}) \\ &\cdot [r(x1_{j+1}, x2_{j+1}, b_k) - r(x1_{j+1}, x2_{j+1}, b_{k-1})] \end{align} $$
Når skaden involverer tre eller flere tilstøtende soner:
$$\begin{align} p_i = p(x1_j, x2_{j+n-1}) &\cdot [r(x1_j, x2_{j+n-1}, b_k) - r(x1_j, x2_{j+n-1}, b_{k-1})] - p(x1_j, x2_{j+n-2}) \\ &\cdot [r(x1_j, x2_{j+n-2}, b_k) - r(x1_j, x2_{j+n-2}, b_{k-1})] - p(x1_{j+1}, x2_{j+n-1}) \\ &\cdot [r(x1_{j+1}, x2_{j+n-1}, b_k) - r(x1_{j+1}, x2_{j+n-1}, b_{k-1})] + p(x1_{j+1}, x2_{j+n-2}) \\ &\cdot [r(x1_{j+1}, x2_{j+n-2}, b_k) - r(x1_{j+1}, x2_{j+n-2}, b_{k-1})] \end{align} $$
og der r(x1, x2, b0) = 0
1.1 Faktoren p(x1, x2) skal beregnes ved følgende formler:
Total normalisert maks skadelengde: Jmaks = 10/33
Knekkpunkt i fordelingen: Jkn = 5/33
Kumulativ sannsynlighet ved Jkn: pk = 11/12
Maksimum absolutt skadelengde: lmaks = 60 m
Lengde der normalisert fordeling slutter: L* = 260 m
Sannsynlighetstetthet ved J: = 0:
$$b_0 = 2 \left(\frac{p_k}{J_{kn}} - \frac{1-p_k}{J_{\text{maks}} - J_{kn}} \right)$$
Når Ls ≤ L*:
$$\begin{align} J_m &= \min \Big \{ J_{\text{maks}}, \frac{l_{\text{maks}}}{L_s} \Big \} \\ J_k &= \frac{J_m}{2} + \frac{1 - \sqrt{1 + (1 - 2p_k) b_0 J_m + \frac 14 {b_0}^2 {J_m}^2}}{b_0} \\ b_{12} &= b_0 \end{align} $$
Når Ls > L*:
$${J_m}^* = \min \Big \{ J_{\text{maks}}, \frac{l_{\text{maks}}}{L^*} \Big \}$$
$$\begin{align} {J_k}^* &= \frac{{J_m}^*}{2} + \frac{1 - \sqrt{1 + (1 - 2p_k) b_0 {J_m}^* + \frac 14 {b_0}^2 {J_m}^{*2}}}{b_0} \\ J_m &= \frac{{J_m}^* \cdot L^*}{L_s} \\ J_k &= \frac{{J_k}^* \cdot L^*}{L_s} \\ b_{12} &= 2 \left(\frac{p_k}{J_k} - \frac{1 - p_k}{J_m - J_k} \right) \\ b_{11} &= 4 \frac{1 - p_k}{(J_m - J_k) J_k} - 2 \frac{p_k}{{J_k}^2} \\ b_{21} &= -2 \frac{1 - p_k}{(J_m - J_k)^2} \\ b_{22} &= -b_{21} J_m \end{align}$$
Den dimensjonsløse skadelengden:
$$J = \frac{(x2 - x1)}{L_s}$$
Den normaliserte lengden av en avdeling eller gruppe med avdelinger:
Jn skal regnes som den som er minst av J og Jm
1.1.1 Der ingen av avgrensningene av den aktuelle avdelingen eller gruppen med avdelinger sammenfaller med det aktre eller forre endepunktet:
$$\begin{align} J \leq J_k &: \\ p &(x1,x2) = p_1 = \frac 16 J^2 (b_{11}J + 3b_{12}) \\ J \gt J_k &: \\ p &(x1,x2) = p_2 = - \frac 13 b_{11} {J_k}^3 + \frac 12 (b_{11}J - b_{12}) {J_k}^2 + b_{12}JJ_k - \frac 13 b_{21} ({J_n}^3 - {J_k}^3) + \\ \frac 12 &(b_{21}J - b_{22})({J_n}^2 - {J_k}^2) + b_{22}J (J_n - J_k) \end{align}$$
1.1.2 Der den aktre avgrensningen av den aktuelle avdelingen eller gruppen med avdelinger sammenfaller med det aktre endepunktet, eller den forre avgrensningen av den aktuelle avdelingen eller gruppen med avdelinger sammenfaller med det forre endepunktet:
$$\begin{align} J \leq J_k &: \\ p &(x1,x2) = \frac 12 (p_1 + J) \\ J \gt J_k &: \\ p &(x1,x2) = \frac 12 (p_2 + J) \end{align} $$
1.1.3 Der den aktuelle avdelingen eller gruppen med avdelinger strekker seg over hele oppdelingslengden (Ls):
p(x1, x2) = 1
1.2 Faktoren r(x1, x2, b) skal bestemmes ved følgende formler:
$$r(x1,x2,b) = 1 - (1-C) \cdot \left[ 1 - \frac{G}{p(x1,x2)} \right]$$
der
$$\begin{align} C &= 12 \cdot J_b \cdot (-45 \cdot J_b + 4) \text{, der} \\ J_b &= \frac{b}{15 \cdot B} \end{align} $$
1.2.1 Der den aktuelle avdelingen eller gruppen med avdelinger strekker seg over hele oppdelingslengden (Ls):
$$G = G_1 = \frac 12 b_{11} {J_b}^2 + b_{12} J_b$$
1.2.2 Der ingen av avgrensningene i den aktuelle avdelingen eller gruppen med avdelinger sammenfaller med det aktre eller forre endepunktet:
$$\begin{align} G &= G_2 = - \frac 13 b_{11} {J_0}^3 + \frac 12 (b_{11} J - b_{12}) {J_0}^2 + b_{12} JJ_0 \text{, der} \\ J_0 &= \min (J,J_b) \end{align} $$
1.2.3 Der den aktre avgrensingen til den aktuelle avdelingen eller gruppen med avdelinger sammenfaller med det aktre endepunktet, eller den forre avgrensningen til den aktuelle avdelingen eller gruppen med avdelinger sammenfaller med det forre endepunktet:
$$G = \frac 12 (G_2 + G_1 \cdot J)$$
