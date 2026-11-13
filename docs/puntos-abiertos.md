# Graal: puntos abiertos

Actualizado: 2026-11-10

Lo que falta decidir o construir. Lo ya cerrado está en `decisiones.md`, y las
reglas vigentes en `reglas-graal.md`.

## Decisiones de diseño pendientes

**1. Las 39 habilidades cuyo efecto lo elegimos nosotros.** Ya no quedan
habilidades sin efecto: las 1044 hacen algo. Pero las 39 que el importador no
sabía traducir se llenaron **a mano** el 2026-11-09 (34 con quitar maná, 5 con
esquivar, en `data/personajes.json`), y eso rompe media regla de la casa: del
dato salía *qué* efecto tiene cada habilidad y del juego *cuánto* da. Nueve de
esas 39 decían en FGO "no actúas este turno" y hoy quitan maná.

Era la decisión correcta, porque una habilidad vacía gastaba el turno a cambio
de nada y la IA nunca la usaba, así que solo la pisaban las personas. Pero deja
dos cosas pendientes:

- **Lo que de verdad dicen esas 39 sigue sin existir en el combate**, y es lo
  mismo que antes: aturdir, retrasar o sellar el Noble Fantasma (`donotAct`,
  `delayFunction`, `donotNoble`, `selfturnendFunction`, `donotSkill`: unas 17
  funciones), resistir estados, que aquí no hay (`upTolerance`,
  `upGrantstate`, `subState`, `reduceHp`, `deadFunction`...: unas 14), y
  provocar (`upHate`, 2). Las de "no actúas" son las más peligrosas de todas:
  en un combate de 9 turnos quitar un turno es quitar el 11% de la partida, y
  encadenarlo es dejar a alguien sin jugar. Si algún día entran, hay que
  decidir antes si se resisten y cuántas veces seguidas, y entonces estas
  fichas a mano se pueden revisar.
- **Bajar el crítico sigue siendo traducible y sigue sin entrar** (16
  funciones: `downCriticalrate` 8 + `downCriticalpoint` 8). Nacería casi
  muerto: la probabilidad base es del 15%, así que lo máximo que puede hacer
  es quitar esos 15 puntos, y el crítico ya es de los efectos más flojos.
  Además necesitaría un suelo propio, porque hoy un -0.50 dejaría la
  probabilidad en negativo. Si entrara, se le podría devolver su efecto a
  alguna de las 39.
- **Quitar maná ahora lo llevan 41 personajes** y rinde un 54.0%, contra el
  64.9% que rendía con 7. Paga su turno, pero con poco margen; si alguna vez
  se toca su valor (60, el espejo de `MANA`), la medida hay que rehacerla con
  los 41 y no con los 7.

**Cómo se llegó aquí**, que es la mitad de la información: Eran 159 de 1044 (el 15.2%),
en 131 personajes, y el 2026-11-09 se midió de qué estaban hechos y se tradujo
la parte fácil: **la tanda 1**, lo que ya era uno de nuestros cinco efectos con
otro nombre. Cargar más rápido el Noble Fantasma (`upDropnp`, `hastenNpturn`,
`gainNpBuffIndividualSum`, 100 funciones entre los tres) es maná, y más vida
máxima (`addMaxhp`, `upGainHp`) es curar. Quedaron 117 huecos y solo un
personaje con los tres vacíos. Ver *Las habilidades que no hacían nada* en
decisiones.md.

Lo que quedaba entonces eran dos cosas distintas, y conviene no mezclarlas:

- **Perillas que el combate no tiene**: esquivar un golpe entero (`invincible`,
  `avoidance`, `avoidState`: 38 funciones), aguantar un golpe mortal (`guts` y
  `gutsFunction`: 48), provocar (`upHate`: 18) y resistir estados, que aquí no
  existen. Se pueden aproximar a las que sí tenemos (esquivar ≈ defensa,
  aguantar ≈ curar), y eso recortaría los 117 a 115 habilidades vacías dejando
  igual al único personaje que las tiene todas vacías. Es poco, y ya no es
  traducir: es decidir que una cosa pasa por otra. Por eso se paró aquí.
- **Los que apuntan al rival**, que son el grupo grande: 244 funciones a
  `enemy` y `enemyAll` (aturdir, bajarle el ataque o la defensa, sellarle el
  Noble Fantasma). Están fuera por diseño y no por descuido. El atajo que ya
  estaba apuntado aquí sigue en pie: en un duelo, bajarle el ataque al rival es
  lo mismo que subirse la defensa. Pero **en Graal una batalla puede tener
  hasta cuatro**, así que la equivalencia solo vale en los duelos y habría que
  decidir qué hace en una batalla de tres o cuatro.

El único que se quedó con las tres habilidades vacías fue **Gilles de Rais
(Caster)**: su kit entero son debuffs al rival (`downNpdamage`,
`selfturnendFunction`) y resistencia a estados. Ese no salía de ninguna tabla,
y acabó como se dijo aquí: a mano en `personajes.json`, que es para lo que
existe. Hoy lleva bajar el ataque (eso sí se tradujo), quitar maná y esquivar.

**1.b La IA mide mal la mitigación, y eso tiene un número con nombre.**
`BAJAR_ATAQUE` vale 0.40 y a ese valor **llevarla es peor que llevar un hueco
vacío** (41.0% contra sí misma con la habilidad muerta). A 0.50 la habilidad
rinde un 66.4% honrado, pero el plantel se va de 146 a 158 personajes fuera de
la banda y alguien llega al 97.2%, así que se quedó 0.40 por la regla del
plantel. Es el único número del combate puesto a sabiendas de que la IA lo
juega regular.

El fondo no es el valor: es que la IA cuenta la mitigación como si valiera lo
mismo que el daño, y en este combate no, porque el que pega más mata antes y
reducir el daño que recibes alarga la pelea en vez de ganarla. Es la misma
razón por la que *defenderse es una acción débil*. Arreglar eso en `ai.py`
(que la mitigación valga menos que el daño, medido) es lo que permitiría subir
`BAJAR_ATAQUE` a su sitio, y probablemente mueva también a `defensa` y a
`curar`.

**2. Lo que le queda al idioma.** El catálogo ya está hecho (ver
`decisiones.md`): español e inglés en `bot/data/textos.json`, y el idioma lo
elige quien crea la guerra. Quedan tres cosas pequeñas:

- **Lo privado en el idioma de cada jugador.** Hoy la ficha y los avisos
  privados van en el idioma de la guerra. Discord manda el idioma del usuario
  en cada interacción, así que se puede hacer; la duda es si conviene, porque
  un jugador vería su ficha en inglés y el combate en español.
- **Cambiar el idioma de una guerra ya empezada**, que hoy no se puede.

También queda decidir si el español del catálogo lleva acentos. Hoy no los
lleva porque el registro de batalla se imprime en la consola de Windows desde
el simulador; en Discord se verían bien.

**3. Alianzas mecánicas.** Hoy un beneficio se le puede dar a cualquiera de la
batalla, que es lo que hace jugables los pactos sin diseño nuevo. Queda
abierta la versión ambiciosa: un pacto declarado en el bot, con lo que eso
permitiría (efectos en área sobre los aliados, ver sus decisiones, romper el
pacto con consecuencias).

~~**4. Sellos de Comando dentro del combate.**~~ **Decidido y construido el
2026-11-10**: tres usos (llenar el maná, curar, apagar los enfriamientos), uno
por batalla, no gastan el turno. Los 5 de Jeanne ya sirven. Ver *Los Sellos de
Comando* en `decisiones.md`. Lo que queda de aquí es que **la IA no los usa**,
y por eso `CURACION_DEL_SELLO` no está medido: va con el punto 1 del inventario,
al final de este documento.

**5. Objetos.** Ganar un combate NPC puede soltar un objeto que ayuda.
Propuesta sin cerrar: consumibles de un solo uso, máximo 1 o 2 por batalla.
Falta el catálogo y qué hacen.

**6. Ritmo del día.** Quién elige el tiempo de preparación y el máximo del día
al crear la guerra (el creador o una votación), qué valores se ofrecen para el
máximo y si ese máximo incluye la preparación.

**7. La recompensa de la guerra.** Ya está decidido **cuándo** se entrega el
Grial: cuando juegan 4 personas de verdad o más y el que queda en pie es una
de ellas (ver `decisiones.md`). Falta **qué es** el Grial: qué recibe quien lo
gana. Cristopher mencionó tener una idea para que la recompensa tenga sentido
con el límite de 7 jugadores por guerra. Mientras no exista, el bot ya dice en
cada guerra si está en juego o no, así que la condición se puede jugar aunque
el premio no esté definido.

**8. Qué tan bien juega la IA sustituta.** Reemplaza a quien no responde en 5
minutos. Como 2 derrotas eliminan, de esto depende cuánto riesgo tiene
desconectarse. Hoy juega con una heurística simple en `src/game/ai.py`: mide
cada habilidad en "ataques" y solo usa lo que devuelve más de uno, y nunca
regala un beneficio a otro.

**9. Ajuste manual de velocidad por personaje.** Hoy la velocidad la da solo la
clase, así que todos los Assassin son igual de rápidos. Queda por decidir si
se añade un campo opcional de −0.10 a +0.10 en la ficha para retocar a mano
los personajes que importen.

## Pendiente de construir

- **Los efectos de los Nobles Fantasmas.** El nombre, el rango y el tipo están
  para los 348 y se ven en la ficha, pero todos hacen lo mismo: ×3 de daño a
  un objetivo. Los datos traen sus efectos igual que los de las habilidades,
  así que la traducción ya existe y se puede reusar; lo que falta es decidir
  si un Noble Fantasma puede hacer algo que una habilidad no. Hasta entonces
  la ficha dice la verdad: el efecto que describe es el nuestro, no el de FGO.
- ~~**El menú de habilidades en Discord.**~~ Hecho: dos desplegables (cuál y
  sobre quién), con el nombre y lo que hace cada una. Lo que **no** sale
  todavía es el enfriamiento que le queda a las que no se pueden usar: el
  desplegable solo trae las listas, así que una habilidad enfriándose
  desaparece sin decir cuándo vuelve. Está en `ficha.*`, falta traerlo aquí.
- ~~**Guardar las guerras en SQLite.**~~ Hecho: `src/repositorio.py`, ver
  `decisiones.md`. Lo que queda por guardar **son las batallas**, y ahora sí
  se puede: desde que existe `game/combate.py` una batalla dura lo que tarde
  la gente en decidir, no un instante. Hoy viven en memoria y un reinicio las
  pierde (el vigilante acaba el día con la IA, ver "Una batalla en curso vive
  en memoria" en `decisiones.md`). Las tablas `batallas`, `participantes` y
  `decisiones` ya están en el esquema esperando.
- ~~**Solo contaba la derrota del primero que caía.**~~ Arreglado el
  2026-11-07, lo encontró Cristopher probando: `anotar_batalla` apuntaba
  `caidos[0]` y nada más, así que en una batalla que seguía después de la
  votación el segundo Servant que caía salía gratis. El simulador tenía el
  mismo error, así que la medida de justicia se había hecho con una derrota de
  menos; se volvió a medir.
- **La votación nunca para una batalla, y eso acorta la guerra a la mitad.**
  Lo descubrió el arreglo de arriba: midiendo 12 000 batallas, **todas acaban
  con un solo Servant en pie** (un grupo de 2 deja 1 derrota, uno de 3 deja 2,
  uno de 4 deja 3; el 100% de las veces, sin excepción). No es un azar: la
  batalla sigue si *alguien* vota por seguir, y `ai.votar_continuar` sigue
  cuando está mejor que su mejor rival, así que **el que va ganando siempre
  vota seguir** y siempre hay uno que va ganando. La votación solo puede
  frenar algo entre personas.

  La consecuencia es de diseño, no de código: una guerra dura ahora **3.9
  días** en vez de 8.7, el nivel máximo que se alcanza es ~12 y la tercera
  habilidad (nivel 15) no llega nunca. La mesa sigue siendo justa (14.0% para
  una persona contra 6 bots con 5 semillas x 200, 56.8% con cuatro personas),
  así que no es urgente, pero hay que decidir qué guerra se quiere:
  - dejarlo: guerras cortas y feroces, donde un grupo de 4 casi lo resuelve;
  - que la IA vote parar más (por ejemplo si no es el más fuerte *con holgura*,
    o si le queda poca vida), que es cambiar una línea y volver a medir;
  - o que la batalla acabe en la primera caída salvo que **todos** voten
    seguir, que es cambiar la regla y contradice `reglas-graal.md`.

  Antes de tocar nada hay que medir, y la medida de justicia necesita varias
  semillas.
- **El botón de listo *de antes del combate* no existe.** Las reglas piden uno
  que dure 5 minutos y que baste con que lo pulse un jugador, y que si no lo
  pulsa nadie el combate se aplace (`reglas-graal.md`, "Batalla por turnos").
  Lo que hay hoy es el "ya acabé mi día", que es otro: cuando se cierra la
  preparación la batalla empieza directamente, y desde el 2026-11-09 **el
  último en decirse listo cierra el día él solo** (ver *La cuarta puerta* en
  decisiones.md), así que el "empieza directamente" es más literal que antes.
  Eso hace que este punto importe menos, no más: nadie espera a un clic del
  creador. En la práctica el plazo de 5
  minutos por turno cubre lo que ese botón protegía (nadie se queda esperando
  a un ausente), así que la pregunta abierta es si hace falta de verdad o si
  era una forma de decir lo mismo.
- ~~**El menú de combate no se refresca solo.**~~ **Resuelto el 2026-11-09**,
  y era un fallo de verdad y no una incomodidad: Cristopher lo probó con un
  amigo y el que no cerraba el turno no veía nada, así que tampoco sabía que
  tenía que refrescar. Se hizo lo que decía este punto: el Cog guarda la última
  interacción de cada uno (`self.mesas`) y al resolverse el turno les reescribe
  el menú con `edit_original_response()` y les manda el turno. Ver *Repartir el
  turno entre los que pelean* en decisiones.md. Lo que sigue en pie es el
  límite de los 15 minutos: a quien tarde más que eso en volver le queda el
  botón de *Refrescar*, que no se ha quitado.
- **No atacar sigue sin costar nada**, y ahora se ve mejor que antes, porque
  declarar el ataque pasó a ser un botón del jugador en vez de un hueco que
  rellenaba la formación de batallas. Quien entrena sus 4 combates, no declara
  a nadie y nadie le declara, descansa el día entero y sube de nivel gratis.
  Lo que lo limita hoy es que los bots siempre atacan, así que en una guerra
  con bots es difícil que te dejen en paz; en una de 7 personas, no. Las
  opciones son que descansar cueste algo, que la formación empareje a los que
  descansan, o dejarlo como sabor. Antes de tocarlo hay que medirlo.
- **La IA no aprovecha lo que conoce al declarar.** Ahora que el Servant ajeno
  es secreto hasta pelearlo (ver `decisiones.md`), un bot declara su ataque al
  azar igual que antes, así que no juega con ventaja pero tampoco con cabeza:
  tras un día de batallas conoce clases que podría usar para buscar el lado
  bueno del triángulo. Hacerlo la vuelve más fuerte, así que antes de tocarlo
  hay que medir la mesa otra vez: hoy una persona sola contra 6 bots gana el
  15–17% con un 14.3% esperado, y ese margen es lo que no se puede perder.
- **Qué se ve de un Servant que cae.** Al morir su Master queda eliminado y su
  ficha sigue oculta para quien no le peleó. Es defendible (no cambia ninguna
  decisión futura) pero queda raro al contar la guerra; si alguna vez hay un
  resumen final, ahí sí deberían verse todos.
- ~~**Los comandos de batalla**: botón de listo, menú de acciones oculto,
  turnos, votación y turno especial.~~ Hecho: `src/game/combate.py` y el
  `MenuCombate` de `commands.py`, ver "El menú de combate" en `decisiones.md`.
- **Los plazos que le faltan al vigilante.** El de la ventana de preparación ya
  está (`src/vigilante.py`, ver `decisiones.md`) y los **5 minutos por turno**
  también, desde que existe el menú de combate (`Combate.plazo_cumplido`).
  Queda el **máximo del día**: hoy una batalla puede estirarse turno a turno
  todo lo que la gente quiera, y lo único que la corta es el tope de 60 turnos.
- ~~**Los plazos viven en memoria.**~~ Hecho: `vence_preparacion` se guarda en
  la tabla `plazos` con su guerra, y un plazo que venció con el bot apagado se
  nota en la primera revisión del vigilante al volver.
- ~~**El día no se cierra hasta que el creador pulsa.**~~ **Hecho el
  2026-11-09**: el último en decirse listo cierra la preparación y abre los
  combates. Son cuatro puertas y todas pasan por `cog.cerrar_el_dia`. Ver *La
  cuarta puerta* en decisiones.md. Lo que queda en pie de aquí es que **un menú
  efímero puede ser de ayer**: `MenuAccion` ya se defiende con `dia_del_menu`,
  pero cualquier botón nuevo que cambie el día tendrá que hacer lo mismo, y
  nada va a avisar.
- **Lo que decide el día no es solo el `rng` de la guerra.** El orden en que se
  recorren los Masters cambia de una corrida a otra (Python aleatoriza el hash
  de las cadenas), y con él cambia a quién le toca pelear y a quién descansar.
  Para el juego da igual, pero una prueba que exija una salida concreta falla
  una de cada tres veces; se descubrió al escribir las de la cuarta puerta. Si
  alguna vez hace falta que una guerra sea reproducible de verdad (por ejemplo
  para contar una partida paso a paso), hay que ordenar esos recorridos.

## ¿Hace falta poder saltarse a un ausente?

Resuelto a medias: el vigilante cierra el día cuando se agota la ventana sin
esperar a nadie, así que una persona que no aparece ya no deja la guerra
parada para siempre, solo hasta que venza el plazo. Con 24 horas de ventana,
eso puede ser un día entero de espera.

Queda por decidir si el creador debería poder echar o saltarse a alguien que
no aparece. Yo creo que no: elegir a quién te esperas es una decisión que un
creador podría usar para elegir cuándo le conviene cerrar, y eso es el agujero
de entrenar-y-cerrar otra vez con otro nombre. Lo que sí tendría sentido es
poder acortar la ventana de una guerra ya empezada, que no decide nada por
nadie.

## ~~El efecto MANA no paga el turno que cuesta~~ (resuelto)

**Resuelto el 2026-11-07 quitando el tope de 1 Noble Fantasma por
combate** (ver "El Noble Fantasma se puede repetir" en `decisiones.md`).
El espejo del mana pasó del 23.9% al 68.2% y el plantel a nivel 15 bajó de
166 a 141 personajes fuera de banda. Se deja lo de abajo porque explica
por qué, y porque el diagnóstico — *el mana no escaseaba, era un reloj* —
es el que hay que recordar si alguien vuelve a tocar el costo del Noble
Fantasma o el mana por ataque.

Medido el 2026-11-07, a raíz de una pregunta sobre Semiramis: su primera
habilidad, *Familiar (Dove) D*, da +60 de mana a sí misma con enfriamiento 3.
La pregunta era si 60 es demasiado. **Es al revés: no es demasiado, es
irrelevante, y el turno que cuesta la convierte en una trampa.**

El espejo de siempre (el mismo personaje con la habilidad contra el mismo sin
ella), nivel 5 para que solo haya una habilidad, 30 personajes x 200 combates:

| mana | victorias | usos | su NP | turno | el NP del rival | turno | dura |
|---|---|---|---|---|---|---|---|
| 40 | 49.8% | 0.00 | 93.8% | 6.0 | 94.0% | 6.0 | 10.2 |
| **60** | **27.3%** | 1.00 | 100% | **3.0** | 98.2% | 6.0 | 11.0 |
| 100 | 38.0% | 1.00 | 100% | 2.0 | 95.2% | 6.0 | 10.4 |

La fila de 40 es la línea base y vale como control: la IA solo usa una
habilidad que devuelva más de un ataque (`PAGA_EL_TURNO`), y con 40 de mana la
cuenta no llega, así que no la usa nunca y el espejo sale 49.8%, como debe.

Con 60 sí la usa, **adelanta su Noble Fantasma del turno 6 al turno 3 y pierde
23 puntos de victorias.** Adelantarlo tres turnos vale menos que el ataque que
costó.

**El motivo no es el número, es que el mana no escasea.** Un combate dura unos
10 turnos y se empieza con 20 de mana ganando 15 por ataque, así que *todo el
mundo* llega a los 100 en el turno 6 sin hacer nada especial: el rival suelta
su Noble Fantasma el 94% de las veces igual. Y como el Noble Fantasma se usaba
una vez por combate, el mana que pasaba de 100 se tiraba entero. O sea que el
mana no compraba nada: solo adelantaba algo que iba a pasar igual.

**La IA lo valora mal, y es un error honesto.** `_cuanto_paga` trata el mana
como convertible en daño: `(valor - 5) * (x3 - 1) / 100`, que con 60 da 1.1
ataques y por eso la usa. La cuenta sería correcta si el mana comprara Nobles
Fantasmas; con uno por combate y 100 asegurados, el valor real es casi cero.

Y no es solo Semiramis. Con el plantel entero a nivel 15 (120 personajes), el
mana es **el único efecto por debajo del 50%**, y queda por debajo de no tener
efecto ninguno:

| efecto | personajes | victorias |
|---|---|---|
| curar | 21 | 65.1% |
| ataque | 100 | 61.9% |
| critico | 55 | 57.7% |
| defensa | 18 | 57.1% |
| *ninguno* | 1 | 55.0% |
| **mana** | **60** | **48.6%** |

**Llevar una habilidad de mana es peor que llevar una que no hace nada**,
porque la que no hace nada la IA no la usa. Afecta a 147 de los 349
personajes, el 42% del plantel: es la causa más probable de que el plantel se
abra a nivel 15 (ver "Las habilidades ensanchan el plantel").

### Las salidas, de más barata a más cara

1. **Enseñarle la verdad a la IA**: que una habilidad de mana solo valga lo que
   adelanta *si no fueras a llegar a 100 igual*. Es correcto, es pequeño y deja
   de regalar turnos, pero convierte el efecto en letra muerta: la IA no la
   usaría casi nunca. Sube el espejo del 27% al 50%.
2. **Que el mana escasee**: subir el costo del Noble Fantasma o bajar
   `MANA_POR_ATAQUE` para que llegar a 100 no sea automático. Entonces el mana
   vale lo que la IA cree. Toca el combate entero y hay que recalibrar todo.
3. **Más de un Noble Fantasma por combate**: quitar el tope de `np_usado` y
   dejar que el mana se gaste otra vez. Hace cierta la cuenta de la IA de
   golpe, y además le da al Noble Fantasma el papel que tiene en la serie.
   Cambia mucho el combate.
4. **Darle al efecto MANA un segundo significado** (mana al grupo, robar mana)
   y dejar de usarlo como "adelanta tu Noble Fantasma".

Lo barato (1) es correcto pero tira el efecto a la basura. Lo que arregla el
juego es (2) o (3), y las dos son una recalibración entera.

**Se tomó la 3**, el mismo día. Salió bien y barato: cuatro líneas y la mesa
siguió siendo justa. Lo que costó fue medirlo.

## Lo que destapó quitar el tope del Noble Fantasma

Los tres están medidos en "El Noble Fantasma se puede repetir" (`decisiones.md`).

- ~~**El entrenamiento contra NPC se volvió más fácil.**~~ Resuelto el
  2026-11-07: ver "Los NPC se endurecen y dejan de ser un acantilado" en
  `decisiones.md`. De paso se arregló un acantilado que ya estaba antes, con el
  4.º NPC pasando del 84% el día 3 al 5% el día 7.

  Ojo con una explicación falsa que escribí primero: *las Sombras no tienen
  Noble Fantasma*. No es verdad. `SIN_NOBLE_FANTASMA` solo le quita el nombre
  en la ficha; `puede_noble_fantasma` mira el mana y nada más, así que la
  Sombra lanza Noble Fantasmas igual (medido: 74 contra 52 del jugador en 40
  combates del día 5). Si algún día se quiere que de verdad no tenga, hay que
  **gatear la acción** en `battle.py`, no quitarle el nombre.
- **Un nivel de diferencia pesa más**: del 76.4% al 80.4%, y dos del 82.6% al
  87.2%. No es necesariamente malo —subir de nivel debe notarse— pero si sigue
  creciendo, el que entra tarde a una guerra no tiene nada que hacer. Lo que
  antes decía aquí, que se refuerza porque entrenar renta más, ya no vale:
  endurecer los NPC bajó la XP por día de ~159 a ~139, así que los niveles
  llegan más despacio y las dos cosas se compensan en parte.
- **El 3.º y el 4.º NPC se igualan a partir del día 5.** Los dos chocan contra
  el `FACTOR_MAXIMO` de 0.99 (0.96 y 0.985 endurecidos), así que acaban en la
  misma dificultad: el día 7 se ganan al 70% y al 68%. Es el precio de poner
  un tope plano y se aceptó a sabiendas, porque la alternativa era el
  acantilado. Si molesta, la salida es endurecer *interpolando hacia el tope*
  en vez de multiplicando, de forma que ninguno lo alcance nunca y conserven
  su orden.
- **El crítico es ahora el efecto más flojo**, con un 42.8% en el espejo donde
  el ataque saca 65.5%. No es culpa del cambio: antes estaba en el 42.0% y lo
  tapaba el del mana, que estaba peor. Vale 0.45 de probabilidad durante 3
  turnos con enfriamiento 5, y el enfriamiento largo es la sospecha principal.
  Lo llevan 165 personajes.
- **Dos personajes no tienen ninguna habilidad que haga algo**: Gilles de Rais
  (Caster) y Eric Bloodaxe. Sus tres habilidades existen con su nombre, pero el
  importador traduce los `funcType` de FGO a nuestros cinco efectos y las tres
  se quedan en `NINGUNO`, así que su ficha dice "sin efecto todavía" tres
  veces. A nivel 15 son estrictamente más débiles que cualquier otro, porque
  todos los demás tienen al menos una. Otros 24 tienen solo una de las tres.
  La salida es escribirles un efecto a mano en `personajes.json`, que es
  exactamente para lo que existe ese archivo. Lo destapó una prueba que fallaba
  1 de cada 20 veces según a quién invocara el sorteo.
- ~~**Nueve personajes tienen el Noble Fantasma tapado**~~ **Resuelto el
  2026-11-10**: eran siete con el nombre tapado (y dos con solo el tipo, que no
  se enseña). Se esconde, que es lo práctico: un nombre `???` se limpia al
  leerlo y la ficha dice "Nombre desconocido" y cuenta lo que hace. El Servant
  lo sigue teniendo y lo sigue lanzando. Ver *Cinco preguntas abiertas,
  contestadas* en decisiones.md.

## Balance por afinar

- **No atacar nunca no cuesta nada.** Lo de declarar tarde ya está cerrado
  (se sortea quién entra, y al que no cabe se le busca rival: ver
  `decisiones.md`), pero queda el otro lado: quien no declara solo pelea si
  alguien lo elige, y atacar no da nada más que eliminar rivales, así que se
  puede vivir de que los demás se desgasten. Hace falta un premio por atacar
  —lo natural sería XP por ganar una batalla contra jugadores, que hoy no da
  ninguna— o un coste por descansar. Es diseño nuevo y toca la curva de
  niveles, así que hay que medirlo con `guerras` antes de cerrarlo. Se mide
  cuánto pesa añadiendo al simulador un jugador que nunca declara.
- **Jeanne d'Arc es la más débil del plantel** (25% a 49% de victorias), porque
  le salió una ficha muy de muro (1.27 de vida contra 0.78 de ataque) y sus 5
  Sellos todavía no existen.
- 16 de 349 personajes quedan fuera de la banda 35-65% de victorias a nivel 1.
  Se corrigen retocando su ficha en `personajes.json`, sin tocar el código.
- **Las habilidades ensanchan el plantel, y es lo más gordo que queda por
  afinar.** Con los mismos parámetros (8 rivales al azar x 12 combates), el
  plantel de nivel 1, sin habilidades, tiene una desviación del 7.6% y 16
  personajes fuera de la banda 35-65%. El de nivel 15 sube a 18.6% y **165
  fuera**, del 6.2% al 92.7%. Con las magnitudes de FGO, que no pagaban el
  turno, eran 10.1% y 33: ahora que las habilidades deciden, decide también
  quién tiene tres que funcionan y quién dos huecos vacíos. Tres palancas, no
  excluyentes: traducir los 160 efectos que faltan (punto 1), bajar lo que da
  cada efecto a cambio de que pesen menos, o retocar a mano las fichas de los
  extremos. Se mide con
  `python -m src.simulator --semilla 7 plantel --nivel 15`.
- La primera habilidad, al nivel 5, da un salto grande: cinco niveles de
  ventaja pasan del 97% al 99% de victorias. Habrá que mirar si los
  desbloqueos (5, 10 y 15) siguen cayendo donde deben.
- Los enfriamientos (2 para ataque y defensa, 3 para mana, 5 para crítico y
  curación) se fijaron por lo que pesa cada efecto, no midiendo. Con los
  valores ya puestos se pueden medir: bajar el del crítico o el de la curación
  es la forma más directa de subir a quien se quedó corto.

## Terminar una guerra: lo que quedo fuera

- ~~**No hay forma de que una persona se salga de una guerra sin cerrarla.**~~
  **Hecho el 2026-11-10**: el boton **Rendirse** del menu, que pide pulsarlo dos
  veces. Cuenta como eliminado, la guerra sigue para los demas y el ultimo en
  pie gana; el Grial solo se cobra si se unieron mas de 5 personas. Ver *Cinco preguntas abiertas, contestadas* en
  decisiones.md.

  **Lo que queda de aqui es la medida**, que es lo que este punto ya avisaba:
  rendirse justo antes de perder **ahorra una derrota**, y una guerra de seis se
  vuelve una de cinco a mitad de camino. No se ha medido cuanto pesa eso, porque
  ni la IA ni el simulador se rinden nunca: para medirlo hay que ensenarle a
  `ai.py` a rendirse (por ejemplo con una derrota y poca ventaja) y correr
  `guerras` con varias semillas. Mientras no este medido, lo unico que lo limita
  es que los bots no lo usan.
- **Si el creador desaparece, la guerra no se puede cerrar.** `/terminar-guerra`
  es solo suyo, a proposito, pero una guerra abandonada por su creador se queda
  viva hasta que alguien reinicie el bot con la base de datos a mano. Opciones:
  que la pueda cerrar cualquiera de los que siguen vivos por mayoria, o que el
  bot la cancele sola despues de N dias sin que nadie toque nada.
- **Una guerra cancelada se queda en memoria para siempre.** Igual que una
  acabada jugando: el Cog no las suelta nunca, solo deja de cargarlas al
  arrancar. Con un bot de pocos canales no se nota; con muchos, habria que
  soltarlas.
- **El limite de dias de una guerra sigue sin existir.** Es lo que de verdad
  resolveria "esta guerra se esta alargando", en vez del comando del creador.

## El arte de los Servants: se puede bajar, pero choca con una regla nuestra

Se puede, y la mitad ya estaba hecha. La misma fuente que el plantel (Atlas
Academy) trae en `nice_servant.json` las URLs del arte de carta, en
`extraAssets.charaGraph.ascension`, cuatro por personaje (una por ascension), y
`tools/descargar_imagenes.py` ya existe, es reanudable y guarda en
`data/imagenes/{collectionNo}_{ascension}.png`, que esta en `.gitignore`.

Medido el 2026-11-07 preguntando solo las cabeceras, sin descargar:

- Unos 556 KB por imagen (muestra de 6, de 418 a 665 KB).
- 1396 URLs, las cuatro ascensiones: unos **0.74 GB**.
- Solo la ascension 1: 349 imagenes, unos **189 MB**.
- Ya hay al menos un 404 (el collectionNo 0, Jekyll & Hyde). El script aguanta
  los fallos, los cuenta y se puede volver a correr.

**Lo que hay que decidir primero no es tecnico.** `reglas-graal.md` y
`decisiones.md` dicen los dos, en su primera decision, que este es un proyecto
de fans "con personajes de Fate y **sin arte oficial**". El `charaGraph` es
exactamente el arte oficial del juego. Y los datos y el arte no estan en el
mismo sitio: las estadisticas y los nombres son informacion sobre la obra, y el
arte es la obra. Que el bot subiera esas imagenes a Discord seria volver a
publicarlas, no tener una copia local.

Asi que hay tres caminos y hay que elegir uno a conciencia, no de rebote:

1. **Dejar la regla como esta.** Nada de arte oficial: la carta de invocacion
   se hace con el nombre, la clase, el rango y color por clase. Es lo que el
   codigo hace hoy, y entonces lo que sobra es `descargar_imagenes.py`, que
   habria que quitar o marcar como lo que es.
2. **Cambiar la decision, por escrito.** Si se quiere el arte, que `decisiones.md`
   lo diga y diga hasta donde: por ejemplo copia local para probar, sin subirla
   nunca al repositorio ni a Discord, que es justo como esta pensado el script.
   Lo que no vale es tener una regla que dice una cosa y una herramienta que
   hace otra.
3. **Arte propio o neutro.** Siluetas, iconos de clase o algo dibujado para el
   proyecto. Es mas trabajo y es lo unico que no depende de permiso de nadie.

Nota aparte: hoy **nada en `src/` lee las imagenes**. Las URLs se guardan y el
script las baja, pero el bot no las usa para nada todavia.

(El `imagenes_de()` del importador se perdio en la restauracion del 2026-11-07
y se repuso el mismo dia. Se noto justo por esto: `descargar_imagenes.py`
dependia de el y solo podia fallar. El importador ahora cuenta cuantas fichas
llevan arte, para que una perdida asi se vea en la corrida.)

## Arte: lo que falta

- ~~El collectionNo 0 no tiene arte~~ **Resuelto el 2026-11-09**: era Hyde, la
  forma Berserker de Jekyll, que ya estaba en el plantel con el numero 81. No se
  invoca, asi que se descarta en el importador y el plantel son 348. Ver *El
  plantel son 348: fuera el que no se puede invocar* en decisiones.md. La
  descarga del arte queda completa, 1392 de 1392.
- **Para que sirve la copia local, ahora que el bot enlaza el arte.** El bot ya
  no la necesita: manda la URL de Atlas Academy. Los 737 MB de `data/imagenes/`
  siguen valiendo para mirar el plantel sin red y para armar cosas en local (un
  visor que monte la carta como PNG, por ejemplo), pero conviene decidir si eso
  se va a hacer o si la copia es un peso muerto.
- **Si se bajan solo unas ascensiones, faltan niveles.** El script acepta
  `--ascensiones`, y quien baje solo la 1 se queda sin imagen del nivel 5 en
  adelante. No es un error, pero conviene saberlo.


## El inventario: lo que quedó abierto

Lo cerrado está en `decisiones.md` (*El inventario de los Masters*). Esto es
lo que falta, de más urgente a menos.

**1. El balance de los objetos no está medido, y es lo primero.** La regla de
la casa dice que no se toca un número de balance sin medirlo, y
`VALOR_POR_EFECTO_DE_OBJETO` es un número de balance que **no se midió**: ni la
IA ni el simulador usan objetos, así que no hay con qué medirlo. Lo que se
midió es que la justicia de la guerra no se movió (cuatro semillas de 600,
14.2% / 15.0% / 14.5% / 11.2% contra el 14.3% que toca), y eso solo dice que
los bots no los usan.

Los dos tercios de la habilidad (`FRACCION_DE_LA_HABILIDAD`) salen de un
razonamiento, no de una medida: una habilidad paga el turno y un objeto no, así
que un objeto tiene que dar menos. Para medirlo de verdad hacen falta dos
cosas:

- que `ai.py` sepa usar un objeto (la pregunta es la misma que con las
  habilidades: ¿vale lo que da, medido en ataques?), y
- un modo del simulador, o una bandera de los que hay, que dé objetos a un
  lado y no al otro. La pregunta que importa es **cuántos duelos gana quien
  lleva un objeto encima contra quien no**. Si se acerca al 50%, el número está
  bien; si se va al 70%, sobra valor o sobra el tope.

Mientras eso no exista, cualquier cambio a los valores de los objetos es a
ciegas, y conviene no tocarlos.

**Y desde el 2026-11-10 hay un segundo número en la misma situación**:
`sellos.CURACION_DEL_SELLO` (0.40 de la vida máxima). Mismo problema y misma
cura: la IA no gasta Sellos, así que el simulador no puede decir si están bien,
y hace falta que `ai.py` aprenda a usarlos. Con los Sellos el hueco es peor que
con los objetos, porque los bots **sí los tienen** (tres cada uno) y no los
gastan nunca: una persona que los use juega con una ventaja que no está medida.
Lo que sí sabemos es que ninguno de los tres usos puede romper el combate por
sí solo: llenar la barra adelanta un Noble Fantasma que iba a llegar igual,
curar no pasa de la vida máxima y apagar los enfriamientos no toca ningún
número. Y son tres en toda la guerra.

**2. La mecánica del catalizador.** Pendiente de definir. Hoy la categoría
existe, hay uno por clase en `data/objetos.json`, el inventario los guarda y
usarlos contesta que todavía no hacen nada **sin gastarlos**. Lo que falta es
qué hacen exactamente: si garantizan la clase o solo la hacen más probable, si
hay catalizadores de un Servant concreto (el dato ya tiene `collection_no` para
eso, sin usar), en qué momento del día 1 se usan y qué pasa si dos Masters usan
el mismo (el reparto saca a los siete de una bolsa; forzar una clase le quita
opciones a los demás). Sin eso cerrado no se construye nada más.

**3. Los objetos no entran en la vista de estado ni en el aviso del día.**
Quien se conecte y tenga cuatro objetos encima tiene que abrir el inventario
para enterarse. Ponerlo en `/estado-guerra` es fácil y es privado, así que no
choca con el secreto.

**4. Los bots no usan objetos, ni los sueltan al caer.** Las dos cosas van
juntas: un bot que entrena gana NPC y debería ir juntando objetos igual que una
persona. Hoy no lo hace, y eso es parte de por qué el punto 1 no se puede
medir. Lo que no está decidido es si un Master eliminado deja caer lo que
llevaba.

**5. El tope de 25 no se ha probado contra una guerra larga.** Con cuatro
intentos de NPC al día y una suelta de 0.10 a 0.40, llegar a 25 pide muchos
días. Si las guerras se alargan, lo que hoy es un caso raro deja de serlo y lo
de "se cuenta y se pierde" empieza a doler.

**6. Lo que todavía no puede hacer un objeto.** Los cinco efectos del combate
son los que hay, así que no hay objeto que resucite, que quite un estado, que
dé un turno extra ni que haga nada al rival. Eso está encadenado al punto 1 de
*Decisiones de diseño pendientes* (los 160 efectos sin traducir): en cuanto el
combate tenga perillas nuevas, los objetos las heredan gratis.


## La tienda: lo que quedó abierto

Lo cerrado está en `decisiones.md` (*La tienda y las dos monedas*).

**1. La mecánica del catalizador, que ahora ya se puede comprar.** Esto sube al
primer puesto: antes era una categoría vacía y ahora cuesta 2 o 5 griales de
verdad. Lo que falta decidir:

- **¿Garantiza o solo acerca?** Por 5 griales (tres guerras ganadas) lo
  razonable es que garantice, pero entonces el reparto deja de ser un sorteo
  limpio.
- **El reparto saca a los siete de una bolsa** (`empezar()` los sortea en
  `sin_repartir`). Un catalizador de clase pide una clase que puede no estar en
  la bolsa, y uno de Servant pide a alguien que probablemente no esté. Así que
  hay que decidir si el catalizador **mete** a ese Servant en la bolsa
  (quitando a otro, y entonces le estás quitando opciones a los demás) o si se
  reparte aparte.
- **¿Qué pasa si dos Masters quieren lo mismo?** Dos catalizadores de Saber en
  la misma guerra, o dos del mismo Servant. ¿Gana quien invoca primero? ¿Se le
  devuelve el grial al que no? Devolverlo es lo justo y lo más fácil de
  explicar.
- **¿Cuándo se usa?** Hoy la invocación es del día 1 y cada uno pide la suya
  con `invocar_para`. Lo natural es que el catalizador se gaste ahí, pero
  entonces hay que enseñárselo antes de que invoque, o se le olvida que lo
  tiene.
- **¿Se devuelve si la guerra se cancela?** `/terminar-guerra` cierra sin
  ganador; si alguien gastó un catalizador y la guerra se canceló el día 1, ha
  perdido tres guerras de ahorro por una decisión que no era suya.

Mientras no esté cerrado, usar un catalizador contesta que falta la mecánica y
**no lo gasta**, que es la única parte que no podía esperar.

**2. El balance de los objetos sigue sin medirse** (era el punto 1 de *El
inventario: lo que quedó abierto* y sigue igual de abierto). La tienda no lo
arregla: ahora se sabe **cuánto oro** da una guerra (216 de media, medido), que
es lo que justifica los precios, pero no si un elixir vale lo que da. Para eso
sigue hiciendo falta que `ai.py` use objetos.

De hecho ahora hace falta para dos cosas, porque **los bots ganan oro y no lo
gastan**: en el simulador se les suma igual que a las personas y ahí se queda.
Eso hace que la economía medida sea la de alguien que no compra, y que la
tienda sea, de momento, una ventaja de las personas sobre los bots. Es una
ventaja pequeña (3 o 4 objetos en toda la guerra) pero no es cero, y la medida
de justicia de `guerras` no la ve.

**3. ~~Las monedas no se ven en ningún sitio más que en la tienda.~~**
**Decidido el 2026-11-10: se queda así.** El botón del menú ya lleva el oro en
la etiqueta, y los griales se miran con `/mi-cuenta`, que se hizo el mismo día.

**4. ~~No hay forma de ver los griales fuera de una guerra.~~** **Hecho el
2026-11-10**: `/mi-cuenta` (`/my-account`), privado, dice los griales y las
guerras ganadas, y es el unico comando que funciona en un canal sin guerra.

**5. ~~Nadie puede regalar ni vender nada a nadie.~~** **Decidido el
2026-11-10: no se quiere.** El comercio entre Masters queda descartado, no
aplazado, y por el motivo que este punto ya decía: un pacto deja de ser verbal
si puedes pagarlo, y lo que hace jugables los pactos hoy es que no se pueden
garantizar. Lo que sigue en pie es darle un beneficio a alguien de tu batalla,
que es un pacto que se cumple en el momento o no se cumple.

**6. El oro no se devuelve nunca.** No hay forma de vender un objeto que
compraste por error ni de recuperar oro de una guerra que se canceló. Lo
primero es una decisión (vender al 50% es lo habitual), lo segundo no importa
porque el oro se perdía igual al acabar la guerra.

**7. El tope de 25 del inventario ahora se alcanza antes.** Con la tienda se
puede comprar hasta llenarlo, y entonces las sueltas del entrenamiento se
pierden. Ya estaba apuntado como punto 5 del inventario; la tienda lo hace más
probable.
