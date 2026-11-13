# Graal: reglas de la guerra (borrador v1)

Este documento es la especificación completa. Si lo que quieres es **aprender a
jugar sin saber nada de Fate**, empieza por `como-jugar.md`.

## Resumen

Graal es un bot de Discord donde al menos 7 Masters invocan a un Servant cada uno y pelean por el Grial hasta que queda uno solo. Cada día combina combates contra NPC para entrenar y batallas por turnos con decisiones ocultas contra otros jugadores, en grupos de hasta 4, con espacio para alianzas y traiciones. Un Master queda eliminado tras 2 derrotas contra jugadores.

Es un proyecto de fans sin fines de lucro, con personajes de Fate. **El bot no publica arte oficial**: lo que el jugador ve en Discord es texto, y la carta de un Servant se hace con su nombre, su clase y su rango. El arte del juego se puede tener en copia local para desarrollar y mirar (`tools/descargar_imagenes.py`), pero no se sube al repositorio ni a Discord. Lo marcado como propuesta todavía no está decidido.

## Inicio de la guerra

La guerra no empieza hasta tener 7 Masters inscritos.

- Un jugador abre el lobby con `/crear-guerra` y los demás se inscriben con `/unirse-a-guerra`. Quien tenga Discord en inglés verá esos mismos comandos como `/create-war` y `/join-war`: el nombre lo decide el idioma de cada cliente, y el inglés es el de por defecto.
- Al crear la guerra se elige el idioma, español o inglés, y en ese idioma se escribe todo en ese canal, incluido el registro de la batalla que cada uno lee en privado. Si no se elige, se usa el idioma que Discord trae de quien la crea. Los nombres de los Servants y de los Nobles Fantasmas no se traducen.
- Antes de empezar se eligen dos tiempos: la preparación previa a los combates entre jugadores (30 minutos, 1 hora o 24 horas) y el máximo que puede durar un día.
- Una guerra son exactamente 7 Masters: hay 7 cupos de clase y no se admiten repetidos.
- Los cupos que no llene nadie los puede llenar la IA. Quien abrió la guerra usa `/empezar-guerra` y los que falten entran como Masters que juega el bot, así que se puede jugar solo contra 6 sin esperar a nadie. Hace falta al menos una persona.
- Cuando la guerra empieza, el bot menciona a los jugadores en el canal y deja un botón para que cada uno abra **su menú de acciones**, que solo ve él: sus estadísticas, entrenar y el estado de la guerra. Todo lo que un Master hace en privado se hace desde ahí o con el comando suelto equivalente.
- **El Grial solo se entrega si juegan 4 personas de verdad o más.** Con menos, la guerra se juega igual y se gana igual, pero el premio no cuenta: ganarle a cinco bots diría más de la IA que del jugador. Un bot que queda en pie nunca se lleva el Grial.
- Los bots entrenan sus 4 combates NPC cada día y declaran un ataque al azar, así que suben de nivel al mismo ritmo que un jugador aplicado y la guerra avanza sola.
- **La invocación la pide cada Master, cuando quiera.** Al empezar la guerra el sorteo ya está hecho (los 7 cupos de clase, con su tirada de Ruler), pero no repartido: cada uno llama a su Servant con `/invocar`, o con el botón de su menú, en cualquier momento del día 1. Al cerrarse el día, el ritual se completa solo por quien no lo haya pedido, porque nadie pelea sin Servant y esperar no puede ser una forma de librarse del día.
- El Servant que te toca sale al azar de los que quedan sin repartir, así que **invocar antes o después no cambia lo que te toca**. Esperar solo te cuesta los combates de entrenamiento que no peleas mientras no tienes Servant.
- Hasta que no invoques no puedes entrenar ni declarar un ataque, pero sí te pueden atacar: para cuando se formen las batallas ya tendrás Servant.
- Cada Master invoca un Servant al azar, de nivel 1.
- **Nadie sabe qué Servant lleva nadie.** Ni al empezar ni al invocar: el canal solo anuncia que alguien ha invocado. El Servant de otro Master se descubre **peleando contra él**, y lo que descubres no se olvida: queda visible en tu estado el resto de la guerra. Lo que sí es público de cada uno es su nombre, sus derrotas y sus Sellos.
- Por eso el estado de la guerra es un mensaje privado: no es el mismo para dos personas. Y por eso **el detalle de una batalla solo lo ven quienes pelearon**, desde su menú: las frases nombran las habilidades y el Noble Fantasma, y eso delata al Servant. El canal cuenta quién peleó contra quién y quién cayó.
- La consecuencia buscada es que **declarar un ataque sea una apuesta**: el triángulo de clases decide buena parte del combate, así que atacar a quien no conoces es elegir a ciegas.
- Cada Master tiene 3 Sellos de Comando para toda la guerra, salvo que su personaje diga otra cosa.

## Clases y personajes

Hay 8 clases: Saber, Archer, Lancer, Rider, Caster, Assassin, Berserker y Ruler.

La clase no da estadísticas. Decide dos cosas: el cupo que ocupa en la invocación y la ventaja del triángulo.

- Una guerra tiene 7 cupos, uno por cada clase base (las 7 primeras). Dentro de un cupo, el personaje concreto sale al azar entre los de esa clase.
- El **Ruler** es una invocación especial con un 5% de probabilidad. Cuando aparece, ocupa el cupo de una de las 7 clases base, y esa clase no participa en esa guerra.
- **Triángulo de clases**: Saber vence a Lancer, Lancer a Archer, Archer a Saber. La ventaja da +10% de daño y la desventaja −10%. Rider, Caster, Assassin, Berserker y Ruler quedan neutrales.

Las estadísticas, el rasgo propio, las 3 habilidades y el Noble Fantasma son **del personaje**, no de su clase. El plantel son 348 personajes derivados del export de Atlas Academy, en `bot/data/personajes_generados.json`, y los retoques escritos a mano van en `bot/data/personajes.json`, que se aplica encima emparejando por identificador. Nada de esto está en el código, así que añadir o corregir un personaje no toca el juego.

La velocidad la da la clase, porque los datos de FGO no la traen: Assassin 1.15, Rider 1.10, Lancer 1.05, Saber y Archer 1.00, Ruler 0.95, Caster 0.90, Berserker 0.85. Lo que sobra del presupuesto se reparte entre vida y ataque según la proporción HP:ATK que el personaje tenga en los datos, normalizada por la mediana del plantel. Así cada uno conserva su carácter sin heredar el desequilibrio de un juego hecho para vender invocaciones.

**Presupuesto de estadísticas.** Vida, ataque y velocidad se expresan como multiplicadores sobre una base común (1000 de vida, 100 de ataque y 50 de velocidad en el nivel 1) y **deben sumar 3.00**, con ninguno fuera del rango 0.55 a 1.35. Más vida se paga en ataque o en velocidad. El juego lo valida al cargar: un personaje que no cuadre no entra.

**Rasgos.** Cada personaje tiene un rasgo que mueve un juego fijo de perillas: mana inicial, mana extra por ataque, costo del Noble Fantasma, probabilidad de esquivar al defender, probabilidad de acertar la segunda defensa seguida, número de Sellos, si puede defender, si golpea antes a quien no se defiende y si ataca al azar. Un personaje nuevo solo puede combinar estas perillas, así que no puede inventar una regla que rompa el combate.

## Ciclo de juego

Cada día de juego recorre cinco fases y termina cuando acaban todas las batallas; entonces empieza el día siguiente, con los NPC más fuertes.

1. Ventana de preparación: la invocación (solo el día 1), hasta 4 combates NPC y un ataque opcional contra otro Master. Dura 30 minutos, 1 hora o 24 horas, a elegir al crear la guerra.
2. Formación de batallas: primero se cierran las invocaciones que falten, y después los ataques conectados forman un grupo de hasta 4 Masters. Quien no ataca ni es atacado descansa ese día.
3. Botón de listo: 5 minutos; basta con que lo pulse 1 jugador. La IA controla a quien no lo pulse; si nadie lo pulsa, se aplaza.
4. Batalla por turnos: 5 minutos por turno, decisiones ocultas y daño por velocidad. Termina cuando cae un Servant.
5. Cierre: quien cae suma una derrota; con 2 queda eliminado de la guerra. El día termina cuando acaban todas las batallas.

Siguiente día: los NPC son más fuertes.

**Quien abrió la guerra puede cerrar el día cuando quiera**, con `/empezar-batallas` o con el botón rojo de su menú, sin esperar a que se agote la preparación. La ventana es el plazo máximo, no el mínimo: en una guerra entre amigos o de prácticas contra bots no tiene sentido esperar una hora si ya está todo el mundo. Cerrar el día invoca por quien no haya invocado, forma las batallas, las pelea y abre el día siguiente.

**Pero solo cuando todos han acabado su día.** Cada Master dice "Ya acabé mi día" con el botón de su menú, y se anuncia en el canal para que se vea por quién se espera. Mientras falte alguien, el botón de las batallas está apagado. Decirlo cierra tu día de verdad: después ya no puedes entrenar. Los bots están listos desde que se abre el día, porque hacen todo lo suyo entonces, así que en una guerra contra bots nunca hacen esperar. El creador no se espera a sí mismo: pulsar "empezar las batallas" ya es decir que acabó.

Esto es lo que evita que quien abrió la guerra entrene sus 4 combates y cierre el día antes de que los demás entrenen, que medido le doblaba las victorias.

**Y cuando el último dice que acabó, las batallas empiezan solas.** No hace falta que nadie pulse nada más: si al decirte listo ya no queda nadie a quien esperar, ese mismo clic cierra la preparación y abre los combates. El botón del creador sigue ahí, porque hace falta si alguien se dijo listo antes de un reinicio, pero ya no es el que decide. La otra forma de cerrar el día es que se agote la ventana, y esa no espera a nadie: de eso se encarga el vigilante de plazos.

**Cada día, al abrirse, el bot deja otra vez el botón del menú en el canal**, porque hay cosas nuevas que hacer: los 4 entrenamientos vuelven, el ataque hay que planearlo de nuevo y el "ya acabé mi día" hay que volver a decirlo.

**El ataque se planea desde el menú**, con el botón "Planear ataque": un desplegable con los Masters que siguen en pie. De quien no hayas peleado todavía no verás su Servant, solo su nombre y sus derrotas, así que la primera vez eliges a ciegas. **A quién atacas no lo sabe nadie más**, ni el canal ni tu objetivo; el único sitio donde se ve es la etiqueta de tu propio botón, que pasa a decir "Atacas a X". Puedes cambiar de objetivo hasta que se cierre el día, pero no después de decir que acabaste tu día. Atacar es opcional: quien no ataca ni es atacado descansa. Y declarar no garantiza pelear con ese rival: si la cadena de ataques pasa de 4, se sortea quién entra y a quien no cabe se le busca otro.

El tiempo de preparación se elige al crear la guerra: 30 minutos, 1 hora o 24 horas. Cuando se cumple, se realizan las batallas, y el día acaba en cuanto todas terminan. También se fija un tiempo máximo por día: si se agota, las batallas que no han empezado se simulan con la IA y las que ya empezaron se dejan terminar. Propuesta: un día de juego es una ventana de preparación más las batallas que le siguen, y el máximo cuenta desde que empieza.

## Combates contra NPC

Cada día, un Master elige cuántos combates NPC pelear, de 0 a 4: ganar da XP y objetos, perder le cuesta vida en la batalla de ese día.

- Los 4 NPC tienen dificultad creciente: el 1.º es el más fácil y el 4.º el más difícil. Cada uno es un espejo del Servant del jugador multiplicado por un factor (0.88, 0.93, 0.96 y 0.985) y comparte su clase y sus habilidades, así que el triángulo queda neutro y el entrenamiento mide al jugador, no su emparejamiento.
- Todos se hacen más fuertes con cada día de la guerra, un 1% por día, **pero nunca pasan del 0.99**: una Sombra no puede ser un espejo más fuerte que tú. Sin ese tope el 4.º NPC se volvía imposible a mitad de guerra.
- **Los cuatro se pueden ganar siempre, y ninguno es gratis.** El día 1 se ganan en torno al 97%, 90%, 85% y 75%; el día 7, al 91%, 80%, 70% y 68%. Ganar los cuatro da unos 139 XP el primer día y unos 122 el séptimo, así que entrenar rinde algo más al principio.
- No entrenar no es una opción viable: quien no pelea ningún combate NPC se queda al nivel 1 mientras los demás suben, y **no gana ninguna guerra**. Se midió.
- Perder un combate NPC gasta el intento, igual que ganarlo.
- Se pelean con el mismo sistema por turnos y decisiones ocultas; el NPC responde con una IA simple y el resultado es inmediato.
- Ganar da XP y puede soltar un objeto que ayuda. Propuesta: consumibles de un solo uso, con un máximo de 1 o 2 por batalla.
- Perder suma una penalización a la vida con la que el Servant empieza la batalla contra jugadores:

| Derrotas NPC | Vida inicial en la batalla |
| --- | --- |
| 0 | 100% |
| 1 | 75% |
| 2 | 50% |
| 3 | 25% |
| 4 | 10% |

La penalización vale solo para la batalla de ese día. Quien gana esa batalla recupera toda la vida al terminar.

## Formación de batallas

Una batalla reúne a todos los Masters unidos por ataques declarados, con un máximo de 4.

- Durante la ventana de preparación cada Master puede declarar un ataque contra otro jugador. Es opcional.
- Cada ataque une al atacante con su objetivo. Si A y B atacan a C, los tres pelean juntos; si A ataca a B y B ataca a C, también.
- Esto nivela el juego: si varios eligen al mismo jugador, todos entran en una batalla con más gente.
- Dentro de la batalla cada Master elige a quién atacar en cada turno, así las alianzas y las traiciones ocurren ahí.
- Quien no ataca ni es atacado descansa ese día, sin penalización.
- Si una cadena de ataques supera los 4 Masters, **se sortea quién entra**: el orden de declaración no decide nada. Declarar antes o después da exactamente lo mismo.
- **Declarar un ataque es comprometerse a pelear.** Al Master que no cabe en su cadena se le busca otro rival: primero uno libre —de los que no atacan ni son atacados—, y si no hay ninguno, otro atacante que tampoco cupo. Solo descansa si no queda nadie con quien pelear. Quien es atacado así no lo eligió, pero el combate se inicia igual, como con cualquier ataque.

## Batalla por turnos

En cada turno los Masters eligen una acción en secreto, con un máximo de 5 minutos, y el daño se aplica en orden de velocidad.

- Antes de empezar hay un botón de listo que dura 5 minutos. Debe pulsarlo al menos 1 jugador: la IA controla a quienes no lo hagan, y si nadie lo pulsa el combate se aplaza.
- Cada Servant empieza la batalla con 20 de mana.
- Cada turno se elige una acción y, si hay varios rivales, un objetivo. Si un Master no responde en 5 minutos, el combate pasa a la IA; puede volver a unirse mientras su rival elige su acción.
- El más rápido actúa primero, tanto para atacar como para usar habilidades, por lo que subir de nivel da ventaja de orden y hace que el sistema de niveles importe.
- La velocidad también ayuda a **esquivar sin defenderse**: quien es más rápido que su atacante esquiva con una probabilidad igual al 60% de su ventaja relativa de velocidad, con un tope del 30%. Un Servant un 20% más rápido esquiva el 12% de los golpes. Este número está calibrado contra el plantel completo para que las 8 clases ganen entre el 47% y el 52% de sus combates: con un valor menor la velocidad no valía nada, y con uno mayor las clases lentas se hundían.
- Si un ataque no conecta porque el objetivo ya cayó ante un ataque más rápido, el atacante solo suma el mana y el ataque no se redirige a otro.
- El daño varía ±30% en cada golpe y hay un **15% de probabilidad de crítico**, que multiplica el daño por 1.8. Sin esto el combate es determinista: el de mayor nivel gana siempre, y la clase y las decisiones dejan de importar.

| Acción | Efecto | Mana |
| --- | --- | --- |
| Atacar | Hace el daño asignado al Servant | +15 |
| Defender | Reduce 50% el daño recibido y tiene 10% de evitarlo por completo. La segunda defensa seguida solo tiene 30% de éxito y, si falla, pierde el turno | +20 |
| Habilidad | Cada Servant tiene 3, que se desbloquean a los niveles 5, 10 y 15. Gasta el turno, no cuesta mana y tiene enfriamiento | +10 |
| Noble Fantasma | ×3 de daño a un objetivo. **Sin tope: se repite cada vez que se junte el mana** | −100 |

Con 20 de mana inicial, el Noble Fantasma exige 4 defensas o 6 ataques, así que el primero se lanza entre el turno 5 y el 7, normalmente el 6 si se alternan ataque y defensa. En un combate de unos 10 turnos eso da para uno o dos, y para más si el Servant tiene habilidades de mana.

**No hay máximo.** Lo hubo —uno por combate— y era un error: como llegar a 100 de mana estaba asegurado en el turno 6, el mana no era un recurso escaso sino un reloj, y en cuanto soltabas el Noble Fantasma dejaba de valer nada. Eso convertía las habilidades de mana en una trampa: las llevan 147 de los 349 personajes y les costaban la mitad de sus victorias. Medido, y explicado en `decisiones.md`.

Del Noble Fantasma, cada Servant tiene su **nombre y su rango** (Excalibur, rango A), que salen de los datos y se ven en la ficha. Lo que hace es hoy el mismo para todos; que cada uno tenga su efecto está en `puntos-abiertos.md`.

## Sellos de Comando

Cada Master tiene **3 Sellos de Comando para toda la guerra** (5 si su personaje
lo dice, como Jeanne d'Arc). Se gastan **dentro de una batalla**, desde el menú
de combate, y **no cuestan el turno**: después de gastar uno sigues teniendo que
elegir tu acción. Son el recurso más escaso del juego: un objeto se vuelve a
comprar y una habilidad se vuelve a enfriar, pero un Sello gastado no vuelve.

Hay **tres usos** y nada más:

| Sello | Qué hace |
| --- | --- |
| Llenar el mana | Deja la barra en el costo del Noble Fantasma: lo puedes lanzar este mismo turno |
| Curar | Recupera el 40% de la vida máxima |
| Habilidades listas | Apaga los enfriamientos, así que puedes repetir una habilidad ya usada |

**Solo uno por batalla**, aunque te queden tres: si no, los tres Sellos de la
guerra se gastarían en un mismo turno y serían una decisión en vez de tres. El
tope por batalla vuelve con el día; los Sellos gastados no vuelven nunca.

Lo que un Sello **no** hace es darte una acción extra, que estaba propuesto. Un
turno se resuelve con las decisiones de todos a la vez, así que "actúas otra
vez" no es un efecto: es un turno dentro de un turno, y eso sería una regla
nueva del motor de combate. Llenar la barra de mana es la versión de esa idea
que sí cabe: no te da un turno de más, te deja gastar el que ya tienes en el
Noble Fantasma.

Los bots tienen Sellos y **no los usan**, porque la IA todavía no sabe. Eso es
una ventaja para las personas, y está anotado en `puntos-abiertos.md`.

## Rendirse

Un Master puede salirse de la guerra cuando quiera, desde el botón **Rendirse**
de su menú, que pide pulsarlo dos veces y no se deshace. Cuenta como estar
eliminado: no entra en más batallas, no se le espera para cerrar el día y no
puede ganar. La guerra **sigue para los demás**, y si solo queda uno, ese gana.

El Grial se cobra en ese caso **solo si se unieron más de 5 personas** a la
guerra. Con el mínimo normal de 4, tres personas de acuerdo coronarían a la
cuarta el día 1 y se repartirían un grial por guerra; juntar a seis para eso ya
es más trabajo que jugarla. Una retirada en una guerra que después se pelea no
quita el Grial a nadie: ahí vale el mínimo de siempre.

Si alguien se rinde con su batalla a medias, la IA juega su mano hasta el
final, igual que cuando alguien no contesta a tiempo.

## Habilidades

Cada Servant tiene 3 habilidades, que se desbloquean a los niveles 5, 10 y 15. Siete personajes traen el nombre de su Noble Fantasma tapado con interrogantes en los datos de Atlas, porque en FGO es un secreto de la historia: su ficha dice "Nombre desconocido" y cuenta lo que hace, y el Servant lo lanza igual. El nombre y qué efecto tiene cada habilidad salen de los datos de Atlas Academy, igual que las estadísticas: están en `personajes_generados.json` y no en el código.

**Cada habilidad hace una sola cosa**, de una lista cerrada de diez efectos, que son los que el combate ya tiene. Una habilidad de FGO suele hacer dos o tres cosas a la vez; nos quedamos con la primera que sepamos traducir, y lo demás se pierde a propósito, porque es lo que mantiene el combate legible.

**Cuánto da cada efecto lo decide el juego, no el personaje**: una habilidad de ataque es la misma para todos. Las magnitudes de FGO se descartan, porque allí usar una habilidad no cuesta el turno y aquí sí: un +9% de ataque durante 3 turnos devolvía un tercio del ataque que se dejó de hacer.

| Efecto | Qué hace | Dura | Enfriamiento |
| --- | --- | --- | --- |
| Ataque | El siguiente golpe pega x2.5 | 1 turno | 2 |
| Defensa | Recibe un 35% menos de daño | 3 turnos | 2 |
| Mana | +60 de mana de una vez | — | 3 |
| Crítico | +45 puntos de probabilidad de crítico, sobre el 15% de base | 3 turnos | 5 |
| Curar | Recupera un 12% de la vida máxima | — | 5 |
| Esquivar | El próximo golpe que le llegue no le toca | 2 turnos | 5 |
| Aguantar | Un golpe mortal no le tumba: se queda con el 30% de su vida | 5 turnos | 5 |
| Bajar el ataque | **Al rival**: pega un 40% menos | 3 turnos | 2 |
| Bajar la defensa | **Al rival**: recibe un 50% más de daño | 3 turnos | 2 |
| Quitar mana | **Al rival**: pierde 60 de mana | — | 3 |

Los cinco últimos son del 2026-11-09. Esquivar y aguantar **se gastan de uno en uno y no por turnos**: esquivar es un golpe esquivado, no dos turnos siendo intocable, y aguantar se cobra cuando te salva y no antes. Los tres últimos son los únicos efectos que van **al rival**, y por eso no se los puede poner nadie a sí mismo: una habilidad negativa solo ofrece rivales. Apilar dos bajadas de ataque o de defensa no baja más, porque una sola ya llega al suelo. Quitar mana es el espejo exacto de darlo: 60 puntos, de una vez, y lo que hace es retrasar el Noble Fantasma del rival; a quien tenga el mana a cero no le quita nada.

Lo que **no** existe todavía es aturdir, retrasar o sellar el Noble Fantasma, que son las que piden una regla nueva en el turno, ni nada que resista estados, porque en Graal no hay estados. Las 1044 habilidades del plantel **hacen algo**: las 39 que el importador no sabía traducir se llenaron a mano el 2026-11-09, casi todas con quitar mana, porque una habilidad que gasta el turno a cambio de nada era una trampa para el jugador. El efecto de esas 39 lo elegimos nosotros y no sale de lo que dicen en FGO; está escrito en `data/personajes.json`, a la vista.

Los cinco están puestos para que cada uso devuelva alrededor de un ataque y medio, que es lo que cuesta gastar el turno y algo más. El bono de ataque multiplica también el Noble Fantasma, así que cargar el golpe y soltarlo al turno siguiente es la jugada más fuerte del combate.

El enfriamiento sale del efecto, no del personaje: subir ataque o defensa es el beneficio más pequeño y se puede repetir, mientras que el crítico es el más violento y la curación deshace el daño de un turno entero, así que los dos se pagan caro. Un enfriamiento de N significa que la habilidad vuelve N turnos después de usarse: con 2 se usa en los turnos 1, 4 y 7 de un combate, con 3 en el 1, 5 y 9, y con 5 en el 1 y el 7. En FGO el enfriamiento es de 7 u 8 turnos, que en nuestros combates de unos 9 sería "una vez por combate".

**La duración no cuenta el turno en que se usa**, porque usar la habilidad ya gasta ese turno: si contara, una habilidad de 1 turno no serviría para nada.

En la ficha se ven **las tres desde el primer día**, con las que aún no están desbloqueadas marcadas y con el nivel al que se abren. Saber lo que te viene es parte de decidir cuánto entrenas.

**Usar una habilidad da 10 de mana**, menos que atacar, que da 15 y además hace daño. Sin eso, gastar el turno costaba el ataque *y* el mana, o sea retrasar el Noble Fantasma, y ninguna habilidad de ataque llegaba a pagar lo que cuesta. Se midió.

**A quién se le da.** En Graal no hay equipos: las alianzas son verbales y la batalla es de todos contra todos. Así que lo que en FGO iba "a un aliado" o "a todo el bando" aquí va a **un solo objetivo que elige el Master**, y puede ser cualquiera de la batalla, incluido él mismo; lo que iba "a otro" va a cualquiera menos a él mismo. Regalar un beneficio es una decisión de juego, con todo lo que eso tiene de jugoso para un pacto y para una traición. Si el objetivo elegido ya cayó cuando le toca el turno, el efecto se pierde y no se redirige, igual que un ataque o un Noble Fantasma.

De las 1047 habilidades del plantel, 887 tienen efecto y 160 no: son las que en FGO hacen cosas que nuestro combate no tiene (esquivar un golpe entero, resistir estados, aturdir o debilitar al rival). Esas gastan el turno y no hacen nada, hasta que se decida qué hacer con ellas.

Medido con el simulador: un personaje de nivel 15 con sus habilidades le gana el 65% de las veces a sí mismo sin ellas, y cada una de las cinco familias queda entre el 53% y el 70%, así que ninguna es una trampa ni es la única que vale. El precio es que el plantel se ensancha: con las habilidades en juego, los personajes se parecen menos entre sí que a nivel 1 (ver `puntos-abiertos.md`).

## Objetos e inventario

Un Master lleva objetos encima. **Los suelta el entrenamiento**: al ganarle a un NPC hay una probabilidad de que deje uno, y es mayor cuanto más duro era el NPC (del 10% el primero al 40% el cuarto). Caben 25, y con el inventario lleno lo que sueltas se pierde (se te avisa). **Los objetos duran toda la guerra**: no caducan con el día.

Hay tres clases de objeto, según cuándo sirven.

**Los de combate** mueven las mismas cinco perillas que una habilidad: subir el ataque un turno, subir la defensa, subir la probabilidad de crítico, dar maná o curar. **Usar uno no cuesta el turno**: lo usas y además atacas, defiendes o lanzas el Noble Fantasma, lo que quieras. Por eso dan menos que una habilidad del mismo efecto, que sí gasta el turno entero, y por eso **solo se puede usar uno por batalla**. Sin ese tope, una batalla la ganaría quien llevara más objetos encima y no quien peleara mejor.

**Los de preparación** se usan en el día, antes de que empiecen las batallas, y hacen las tres cosas que el día ya sabía hacer: dar XP de golpe, curarte del desgaste que te dejaron las derrotas contra los NPC, o darte un entrenamiento más. Como el entrenamiento, **no se pueden usar después de decirte listo**: cerrar el día es cerrarlo para ti también.

**Los catalizadores** apuntan a la invocación: la idea es poder pedir una clase concreta, o un Servant concreto, en vez de aceptar lo que te toque del sorteo. **La mecánica está sin cerrar** (ver `puntos-abiertos.md`): hoy existen y se guardan, pero usar uno no hace nada y no te lo gasta.

**Lo que haces con un objeto es tuyo y no se publica.** Usar uno en combate te lo cuenta a ti, en privado, y queda en el detalle de la batalla que solo leen los que estuvieron; al canal no llega. Decir que ese Master usó una gema de maná sería decir algo de lo que lleva encima, y eso es información de la misma familia que el Servant que lleva.

## La tienda: oro y griales

Hay dos monedas y no sirven para lo mismo.

**El oro** lo da ganar: 10, 15, 20 o 30 por cada uno de los cuatro entrenamientos del día (más cuanto más duro el NPC) y 50 por salir en pie de una batalla en la que cayó alguien. Un empate no paga. **El oro se pierde al acabar la guerra**: es de esta guerra y se gasta en esta guerra, en los objetos de combate y de preparación. Medido: una guerra deja unos 216 de oro, que son tres o cuatro objetos.

**Los griales** los da ganar una guerra: 2 al que se lleva el Grial, y **se quedan en tu cuenta para siempre**. Hacen falta cuatro personas de verdad en la mesa para que la guerra entregue el Grial, así que ganarle a seis bots no paga griales. Los griales compran catalizadores: **2 por uno de clase** y **5 por uno de un Servant concreto**, o sea una guerra ganada y tres.

**La tienda solo abre durante la preparación**, y no después de decirte listo. Eso es parte del juego: el objeto con el que vas a la batalla es algo que decidiste llevar antes, no algo que te saca de la nada el que va perdiendo. Los precios se pueden mirar siempre, aunque no puedas comprar.

El catalizador de un Servant concreto se pide **escribiendo el nombre**, porque son 348 y una lista de Discord aguanta 25. Si lo que escribes encaja con varios no se compra ninguno y se te enseñan los que encajan: hay tres Medusa y cinco griales son tres guerras ganadas, así que no se adivina.

**Lo que hace un catalizador al usarlo está sin decidir** (ver `puntos-abiertos.md`). Se pueden comprar y se guardan, pero usar uno todavía no hace nada y no te lo gasta.

## Niveles y progresión

El nivel máximo es 15 y se alcanza en unos 5 días ganando todos los combates NPC; las habilidades se desbloquean a los niveles 5, 10 y 15.

| Nivel | XP acumulada | Desbloqueo |
| --- | --- | --- |
| 5 | 130 | Habilidad 1 |
| 10 | 405 | Habilidad 2 |
| 15 | 805 | Habilidad 3 |

- Para pasar del nivel n al n+1 hacen falta 20 + 5×n de XP.
- XP por victoria NPC: 20, 30, 45 y 70, del 1.º al 4.º. Perder no da XP. Un día con las 4 victorias da 165 XP, así que 5 días de NPC ganados suman 825 XP.
- Al subir de nivel, las tres estadísticas crecen en proporción a la ficha del personaje: 3% por nivel la vida y el ataque, 2% la velocidad. Es un crecimiento plano a propósito: con uno fuerte, el nivel decide el combate solo y la clase, el rasgo y las decisiones dejan de contar.
- Medido con el simulador: un nivel de ventaja da el 76% de las victorias, dos el 83% y tres el 89%. El nivel pesa claramente, pero no garantiza nada. Cinco niveles, que son los que desbloquean la primera habilidad, dan el 99%: ahí sí decide.

## Eliminación y fin de la guerra

Un Master queda eliminado de la guerra tras 2 derrotas contra jugadores; una derrota ocurre cuando su Servant cae en una batalla.

- La batalla termina en cuanto un Servant cae, y su Master suma una derrota.
- En una batalla de 3, cuando uno cae, los dos que siguen vivos eligen entre continuar o terminar. Propuesta: la misma regla para batallas de 4.
- La batalla solo termina si todos los que siguen vivos quieren terminarla. Si alguno quiere seguir, se juega un turno especial: quien eligió seguir recibe al instante el menú de acciones (atacar, defender o usar una habilidad) y quien quiso terminar solo espera a que el otro elija. Después la batalla vuelve a turnos normales. Así, pedir terminar es un voto de confianza en el aliado.
- Los Masters que siguen en pie al terminar recuperan toda la vida.
- La guerra termina cuando queda un solo Master. Se lleva el Grial si es una persona y si en esa guerra jugaban al menos 4 personas; si no, gana la guerra pero sin premio.

## Puntos abiertos

Ver `puntos-abiertos.md`.
