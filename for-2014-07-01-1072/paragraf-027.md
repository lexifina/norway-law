# § 27. Beregning av sannsynligheten for at bare det skadetilfellet som vurderes etter § 26 inntreffer
(1) Sannsynligheten («pi ») for at bare det skadetilfellet som vurderes etter § 26 inntreffer, beregnes slik:
a) Hvis skadetilfellet strekker seg over hele oppdelingslengden Ls: pi = 1
b) Hvis x1 faller sammen med aktre endepunkt: pi = F + 0,5 a p + q
c) Hvis x2 faller sammen med forre endepunkt: pi = 1 – F + 0,5 a p
d) Hvis både x1 og x2 ligger innenfor aktre og forre endepunkt av lengden Ls: pi = a p
(2) I skadetilfeller der x1 og x2 ligger på hver sin side av midtskips, skal verdiene fra formlene i bokstav b, c og d, reduseres med en verdi som fastsettes ved å bruke formelen for «q» i femte ledd nedenfor, og der F2 beregnes ved å sette y = J'/ Jmaks.
(3) Avdelinger med langskipsskott:
a) For avdelinger som er utstyrt med langskipsskott, fastsettes verdien «pi » for vingavdelingen ved å multiplisere verdien fra fjerde ledd med reduksjonsfaktoren «r» i henhold til bokstav c i leddet her.
b) I tilfeller der både en vingavdeling og dens innenforliggende rom skades, skal verdien «pi » beregnes ved å multiplisere verdien fra fjerde ledd i paragrafen her med faktoren (1 – r).
c) Reduksjonsfaktoren «r» beregnes ved følgende formler: $$\begin{align} \text{Hvis } J &\ge 0{,}2 \frac bB: \\ r &= \frac bB \left(2{,}3 + \frac{0{,}08}{J+0{,}02} \right) + 0{,}1, \: \text{hvis} \frac bB \le 0{,}2 \\ r &= \left(\frac{0{,}016}{J+0{,}02} + \frac bB + 0{,}36 \right), \quad \text{hvis} \frac bB \gt 0{,}2 \\ \text{Hvis } J &\le 0{,}2 \frac bB: \end{align} $$ Reduksjonsfaktoren «r» skal beregnes ved hjelp av lineær interpolasjon mellomr = 1 for J = 0og $$r \text{ som for } J \ge 0{,}2 \frac bB \text{, med } 0{,}2 \frac bB \text{ innsatt for } J$$derb = den midlere horisontale avstanden, mellom platehuden og et tenkt plan, målt vinkelrett på senterlinjen, ved dypeste oppdelingsvannlinje. Planet tenkes å skjære langskipsskottenes ytterste punkt i det aktuelle skadetilfellet, og skal regnes parallelt med skottet mellom tverrskipsavgrensingene som brukes i det enkelte skadetilfelle.
(4) Kombinasjoner av avdelinger:
a) Ved beregning av enkeltavdelinger skal formlene etter første og andre ledd brukes.
b) Beregning av «pi » for flere avdelinger samlet, skal utføres på følgende måte: Avdelinger beregnet parvis:pi = p12 – p1 – p2pi = p23 – p2 – p3, osv. Avdelinger beregnet i grupper av tre:pi = p123 – p12 – p23 + p2pi = p234 – p23 – p34 + p3, osv. Avdelinger beregnet i grupper av fire:pi = p1234 – p123 – p234 + p23pi = p2345 – p234 – p345 + p34, osv. Verdienep12, p23, p34, osv.p123, p234, p345, osv. ogp1234, p2345, p3456, osv.skal beregnes etter første, andre og tredje ledd som for en enkelt avdeling der den dimensjonsløse lengden J tilsvarer lengden av den gruppen som består av avdelingene representert ved p's indekser.
c) Faktoren «p» skal settes lik 0 for skadetilfeller som omfatter 3 eller flere avdelinger, hvis den dimensjonsløse lengden av skadetilfellet, fratrukket den forreste og akterste avdelingen, er større enn Jmaks.
(5) Ved beregningen av pi etter første ledd er:
x1 = Avstanden fra aktre endepunkt av «Ls» til det forreste punktet på den aktre avgrensingen av det aktuelle skadetilfellet.
x2 = Avstanden fra aktre endepunkt av «Ls» til det akterste punktet på den forreste avgrensingen av det aktuelle skadetilfellet.
E1 = x1 /Ls
E2 = x2 /Ls
E = E1 + E2 – 1
J = E2 – E1
J' = J – E, hvis E ≥ 0
J' = J + E, hvis E < 0. Maksimal dimensjonsløs skadelengde:
Jmaks = 48/Ls, men ikke større enn 0,24. Vekttall for skadens plassering langskips:
a = 1,2 + 0,8 E, men ikke større enn 1,2. Fordelingsfunksjon for antatt skadeplassering med hensyn på skipets lengde:
F = 0,4 + 0,25E (1,2 + a)
y = J/Jmaks
Hvis y < 1:
F1 = y2 – y3 /3
F2 = y3 /3 – y4 /12
Hvis y > 1:
F1 = y – 1/3
F2 = y2 /2 – y/3 + 1/12
p = F1 Jmaks
q = 0,4 F2 (Jmaks)2
