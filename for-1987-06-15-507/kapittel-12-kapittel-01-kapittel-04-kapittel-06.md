# Regel 7-2 Beregning av faktor si
1 Faktoren si skal bestemmes for hvert tilfelle av antatt fylling som involverer en avdeling eller gruppe med avdelinger, i henhold til følgende betegnelser og bestemmelsene i denne regelen.
θe er likevektsvinkelen i ethvert fyllingstrinn, i grader.
θv er vinkelen, på ethvert fyllingstrinn, der rettende arm blir negativ, eller vinkelen der en åpning som ikke kan lukkes værtett, neddykkes.
GZmaks er maksimum positiv rettende arm (GZ), i meter, opp til vinkelen θv.
Utstrekning er den positive utstrekningen til GZ-kurven i grader, målt fra vinkelen θe. Den positive utstrekningen skal regnes opp til vinkelen θv.
Fyllingstrinn er ethvert atskilt trinn under fyllingsprosessen, inkludert trinnet før (en eventuell) utligning før den endelige likevekten er nådd.
1.1 Faktoren si, for ethvert skadetilfelle ved enhver initiell lastetilstand, di, skal beregnes ved formelen:
$$s_i = \text{minimum} \{ s_{\text{mellomliggende, }i} \text{ eller } s_{\text{endelig, }i} \cdot s_{\text{mom, }i} \}$$
der
smellomliggende,i er sannsynligheten for å overleve alle mellomliggende fyllingstrinn fram til likevektstrinnet, og beregnes i henhold til nr. 2,
sendelig,i er sannsynligheten for å overleve i fyllingstrinnet ved endelig likevekt. Den beregnes i henhold til nr. 3,
smom,i er sannsynligheten for å overleve krengemomenter, og beregnes i henhold til nr. 4.
2 For passasjerskip og lasteskip med kryssfyllingsanordninger skal faktoren smellomliggende, i regnes som den minste av s-faktorene oppnådd fra alle fyllingstrinn inkludert trinnet før en eventuell utligning, og skal beregnes som følger:
$$s_{\text{mellomliggende, }i} = \left[ \frac{GZ_{\text{maks}}}{0{,}05} \cdot \frac{\text{Utstrekning}}{7} \right]^{\frac 14}$$
der GZmaks ikke skal regnes som mer enn 0,05 m og Utstrekning som ikke mer enn 7°. smellomliggende, i = 0 hvis den mellomliggende krengevinkelen overskrider 15º for passasjerskip og 30º for lasteskip.
For lasteskip uten kryssfyllingsanordninger skal faktor smellomliggende, i regnes som én, med mindre administrasjonen vurderer det slik at stabiliteten i mellomliggende fyllingsstadier kan være utilstrekkelig, hvor da ytterligere undersøkelser kreves.
For passasjerskip og for lasteskip med kryssfyllingsanordninger skal tiden for utligning ikke overskride 10 min.
3 Faktoren sendelig, i skal beregnes fra formelen
$$s_{\text{endelig, }i} = K \cdot \left[ \frac{GZ_{\text{maks}}}{TGZ_{\text{maks}}} \cdot \frac{\text{Utstrekning}}{\text{TUtstrekning}} \right]^{\frac 14}$$
der
GZmaks ikke skal regnes som mer enn TGZmaks
Utstrekning ikke skal regnes som mer enn TUtstrekning
TGZmaks = 0,20 m, som for roro-passasjerskip er hvert skadetilfelle som omfatter et roro-rom
TGZmaks = 0,12 m, ellers
TUtstrekning = 20°, for roro-passasjerskip er hvert skadetilfelle som omfatter roro-rom
TUtstrekning = 16°, ellers
$$\begin{align} K &= 1 \text{ hvis } \theta_e \leq \theta_{\min} \\ K &= 0 \text{ hvis } \theta_e \geq \theta_{\text{maks}} \\ K &= \sqrt{\frac{\theta_{\text{maks}} - \theta_e}{\theta_{\text{maks}} - \theta_{\min}}} \text{ ellers} \end{align} $$
der
θmin er 7° for passasjerskip og 25° for lasteskip, og
θmaks 15° for passasjerskip og 30° for lasteskip.
4 Faktoren smom,i får kun anvendelse på passasjerskip (for lasteskip skal smom, i regnes som én) og skal beregnes ved endelig likevekt fra formelen
$$s_{\text{mom, }i} = \frac{(GZ_{\text{maks}} - 0{,}04) \cdot \text{deplasement}}{M_{\text{kreng}}}$$
der
Deplasement er intakt deplasement ved respektiv dypgående (ds, dp eller dl).
Mkreng er maksimum antatt krengemoment som beregnet i henhold til nr. 4.1, og
smom,i ≤1
4.1 Krengemomentet Mkreng skal beregnes som følger:
$$M_{\text{kreng}} = \text{maksimum} (M_{\text{passasjer}} \text{ eller } M_{\text{vind}} \text{ eller } M_{\text{redningsfarkost}})$$
4.1.1 Mpassasjer er maksimum antatt krengemoment som følge av bevegelse av passasjerer, og skal beregnes som følger:
$$M_{\text{passasjer}} = (0{,}075 \cdot N_p) \cdot (0{,}45 \cdot B) \: \: (\text{tm})$$
der
Np er maksimum antall passasjerer som er tillatt å være om bord i seilingstilstanden som tilsvarer den aktuelle største oppdelingsdypgående, og
B er skipets bredde, som definert i regel 2.8.
Alternativt kan krengemomentet beregnes ved å anta at passasjerene er fordelt med 4 personer per kvadratmeter på tilgjengelige dekkområder mot den ene siden av skipet på dekkene der mønstringsstasjoner finnes, og på en slik måte at de produserer det mest ugunstige krengemomentet. Her skal det gås ut fra en vekt per passasjer på 75 kg.
4.1.2 Mvind er maksimum tenkt vindstyrke i en skadesituasjon:
Mvind = (P · A · Z)/9 806 (tm)
der
P = 120 N/m2
A = projisert lateralt areal over vannlinjen
Z = avstand fra midten av det laterale projiserte arealet over vannlinjen til T/2, og
T = respektiv dypgående (ds, dp eller dl).
4.1.3 Mredningsfarkost er maksimum antatt krengemoment forårsaket av utsetting av alle fullastede redningsfarkoster satt ut med daviter, på den ene siden av skipet. Det skal beregnes ved hjelp av følgende antagelser:
.1 alle livbåter og MOB-båter stuet på den siden som skipet har krenget til etter å ha blitt skadet, skal antas å være svingt ut fullastet og klar for nedsenkning
.2 for livbåter som er arrangert for å være fullastet fra den stuede posisjonen, skal maksimum krengemoment under utsetting legges til grunn
.3 en fullastet davit-utsatt redningsflåte koblet til hver davit på den siden som skipet har krenget til etter å ha blitt skadet, skal antas å være svingt ut klar for nedsenkning
.4 personer som ikke befinner seg i redningsredskapene som er svingt ut, skal ikke forårsake ytterligere krengende eller rettende moment, og
.5 redningsredskaper på den siden av skipet som er motsatt av siden som skipet har krenget til, skal antas å være i en stuet posisjon.
5 Usymmetrisk fylling skal holdes til et minimum i overensstemmelse med effektive arrangement. Der det er nødvendig for å korrigere store krengevinkler, skal de implementerte midlene, der det er praktisk mulig, være selvvirkende, men i ethvert tilfelle der det finnes betjeningsinnretninger til utligningsinnretninger, skal disse kunne betjenes fra over skottdekket på passasjerskip og fribordsdekket på lasteskip. Dette utstyret sammen med deres betjeningsinnretninger skal godkjennes av administrasjonen. Egnet informasjon angående bruken av utligningsinnretninger skal gjøres tilgjengelig for skipsføreren.
5.1 Tanker og avdelinger som er inkludert i en slik utligning, skal utstyres med lufterør eller tilsvarende midler med tilstrekkelig tverrsnitt for å sikre at vannstrømmen inn i utligningsavdelingene ikke forsinkes.
5.2 Faktoren si skal regnes som null i de tilfeller der den endelige vannlinjen, idet det tas hensyn til synking, krengning og trim, neddykker
.1 på lasteskip, den nedre kanten på åpninger der progressiv fylling kan finne sted, og slik fylling ikke er tatt hensyn til i beregningen av si-faktoren. Slike åpninger omfatter lufterør, ventilatorer og åpninger som lukkes ved hjelp av værtette dører eller lukedeksler
.2 en del av skottdekket i passasjerskip som anses som en horisontal rømningsvei for samsvar med kapittel II-2, og
.3 på passasjerskip som er underlagt bestemmelsene i regel 1.1.1.1 og bygget før 1. januar 2024, den nedre kanten på åpninger der progressiv fylling kan finne sted, og slik fylling ikke er tatt hensyn til i beregningen av si-faktoren. Slike åpninger omfatter lufterør, ventilatorer og åpninger som lukkes ved hjelp av værtette dører eller lukedeksler.
5.3 Faktoren si skal regnes som null hvis, idet det tas hensyn til synking, krengning og trim, noe av følgende skjer i ethvert mellomliggende trinn eller i endelig fyllingstrinn:
.1 neddykking av en vertikal rømningsluke i skottdekket på passasjerskip og fribordsdekk på lasteskip som er ment for samsvar med kapittel II-2
.2 en hvilken som helst betjeningsinnretning bestemt for betjening av vanntette dører, utligningsinnretninger, ventiler på rør eller på ventilasjonskanaler ment for å opprettholde integriteten til vanntette skott fra over skottdekket på passasjerskip og fribordsdekk på lasteskip, blir utilgjengelige eller ubetjenbare; og
.3 neddykking av en del av rør eller ventilasjonskanaler som er plassert innenfor den antatte skadeutstrekningen og ført gjennom en vanntett avgrensning, hvis dette kan føre til progressiv fylling av rom som ikke antas å være fylt, og
.4 for passasjerskip som er bygget 1. januar 2024 eller senere, neddykking av den nedre kanten på åpninger der progressiv fylling kan finne sted, og slik fylling ikke er tatt hensyn til i beregningen av si-faktoren. Slike åpninger omfatter lufterør, ventilatorer og åpninger som lukkes ved hjelp av værtette dører eller lukedeksler.
5.4 Der det i skadestabilitetsberegningene tas hensyn til avdelinger antatt fylt på grunn av tiltakende fylling, kan imidlertid flere verdier av smellomliggende, i beregnes med antakelse av utligning i ytterligere fyllingsfaser.
5.5 Med unntak av det som er fastsatt i nr. 5.3.1, trenger man ikke vurdere åpninger lukket ved hjelp av vanntette mannlokk og små luker i flukt med dekket, fjernbetjente vanntette skyvedører, lysventiler som ikke kan åpnes, og vanntette atkomstdører og lukedeksler som skal holdes stengt til sjøs.
6 Der horisontale vanntette avgrensninger er plassert over den aktuelle vannlinjen, skal s-verdien beregnet for den nedre avdelingen eller gruppen med avdelinger oppnås ved å multiplisere verdien som fastsatt i nr. 1.1 med reduksjonsfaktoren vm i henhold til nr. 6.1, som representerer sannsynligheten for at områdene over den horisontale oppdelingen ikke vil fylles med vann.
6.1 Faktoren vm skal beregnes ved formelen:
$$v_m = v(H_{j,n,m,}d) - v(H_{j,n,m-1,}d)$$
der
Hj,n,m, er den minste høyden over basislinjen, i meter, innen langskipsutstrekningen til x1(j)... x2(j+n–1) av den m. horisontale avgrensningen som er antatt å begrense den vertikale utstrekningen av fyllingen for de skadde avdelingene som betraktes
Hj,n,m–1, er den minste høyden over basislinjen, i meter, innen langskipsutstrekningen til x1(j)... x2(j+n–1) til den (m – 1). horisontale avgrensningen som er antatt å begrense den vertikale utstrekningen av fyllingen for de skadde avdelingene som betraktes
j representerer det aktre endepunktet av de skadde avdelingene som betraktes
m representerer hver horisontal avgrensning som betraktes, talt oppover fra den aktuelle vannlinjen som betraktes
d er den aktuelle dypgående som definert i regel 2, og
x1 og x2 representer endepunktene av avdelingen eller gruppen med avdelinger betraktet i regel 7-1.
6.1.1 Faktorene v(Hj,n,m,d) og v(Hj,n,m–1,d) skal beregnes ved formlene:
$$\begin{align} v(H,d) &= 0{,}8 \frac{(H-d)}{7{,}8}, \text{ hvis } (H_m - d) \text{ er mindre enn eller lik } 7{,}8 \text{ m} \\ v(H,d) &= 0{,}8 + 0{,}2 \left[ \frac{(H-d) - 7{,}8}{4{,}7} \right] \text{ i alle andre tilfeller} \end{align} $$
der
v(Hj,n,m,d) skal regnes som 1 hvis Hm sammenfaller med den øverste vanntette avgrensningen av skipet innen utstrekningen (x1(j)...x2(j+n–1)), og
v(Hj,n,0,d) skal regnes som 0.
Ikke i noen tilfeller skal vm regnes som mindre enn 0 eller mer enn 1.
6.2 Generelt beregnes hvert bidrag dA til indeksen A ved horisontale oppdelinger ved hjelp av formelen:
dA = pi · [v1 · smin1 + (v2 – v1) · smin2 +... + (1 – vm – 1) · sminm]
der
vm = v-verdien beregnes i henhold til nr. 6.1
smin = den minste s-faktoren for alle skadekombinasjoner oppnådd når den antatte skaden strekker seg nedover fra den antatte skadehøyden Hm.
