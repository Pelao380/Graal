# Graal: decisiones tomadas

Fecha: 2026-11-05

## Proyecto

- Nombre del bot: Graal.
- Bot de Discord público que permite a los usuarios hacer una guerra del santo grial al estilo de Fate.
- Usa personajes de la franquicia Fate. El bot no publica arte oficial; la copia local para desarrollar si se permite (ver *El arte oficial: copia local si, publicarlo no*).
- Sin monetización directa por ahora.
- Lenguaje y librería: Python con discord.py, y SQLite para guardar.
- **Se dice Master y Servant**, como en la serie, no Maestro ni Sirviente. Vale
  para lo que ve el jugador, para los documentos y también para el código, que
  llama `Master` y `Servant` a sus clases y `masters`/`servants` a sus tablas.
  El resto del código sigue en español.
- Archivos del proyecto en C:\Users\criss\Documents\claude\Graal (carpetas `docs` y `bot`).

## Formato de la guerra

- Guerra por temporada o guerra iniciada, con exactamente 7 jugadores (7 cupos de clase).
- Al iniciar se elige el tiempo de preparación antes de los combates entre jugadores: 30 minutos, 1 hora o 24 horas, y el tiempo máximo que puede durar un día.
- Terminada la preparación se realizan los combates; el día acaba cuando todos terminan y empieza el siguiente.
- Si se agota el máximo del día, las batallas que no han empezado se simulan con la IA; las ya empezadas se dejan terminar.
- Un Maestro queda eliminado tras 2 derrotas contra jugadores.
- Cada Maestro tiene 3 Sellos de Comando durante toda la guerra, uno por batalla como mucho, y sus tres usos son llenar la barra de mana, curar y apagar los enfriamientos.

## Cómo se juega desde Discord

Fecha: 2026-11-07.

- **Los comandos llevan el verbo delante**: `/create-war`, `/join-war`,
  `/start-war`, `/war-status`, `/stats` y `/train`, que en español son
  `/crear-guerra`, `/unirse-a-guerra`, `/empezar-guerra`, `/estado-guerra`,
  `/estadisticas` y `/entrenar`. Discord no admite espacios en los nombres,
  así que lo que se leería como "crear guerra" va con guion. Se descartó el
  grupo `/guerra …` que había antes: obliga a pensar primero en el sustantivo.
- **Lo privado va por menú, no por comandos sueltos.** Cuando la guerra
  empieza, el bot menciona a los jugadores en el canal y deja un botón
  "Abrir mi menú"; al pulsarlo, cada uno recibe un mensaje que solo ve él con
  los botones de estadísticas, entrenar y estado de la guerra. Un hueco más,
  desactivado, para el inventario que vendrá.
- Se eligió el botón en el canal en vez del mensaje privado porque el DM falla
  en silencio con quien tenga cerrados los mensajes del servidor, y porque así
  la guerra se ve donde ocurre.
- El menú es de quien lo abrió: si otro pulsa sus botones, el bot le dice que
  no está en esa guerra. Caduca a los 10 minutos y se reabre con el botón del
  canal o con `/estadisticas`.
- **Cada botón llama al mismo método del Cog que su comando.** El estado de la
  guerra está en los dos sitios a propósito, y no hay dos versiones de nada:
  si se desincronizaran, el jugador vería cosas distintas según por dónde
  entrara.
- **Los nombres, las ayudas, las opciones (`preparation`, `language`) y los
  valores del desplegable están en los dos idiomas.** Salen del mismo
  catálogo, con claves `cmd.*`, y los sirve un `Translator` de discord.py que
  se engancha antes de sincronizar. El inglés es el nombre base y el español
  la traducción, por lo del idioma por defecto.
- **Ojo con qué idioma manda en cada cosa**, porque son dos y no coinciden:
  - El **nombre de un comando** lo decide el idioma de Discord de quien mira.
    Un comando se escribe antes de que exista ninguna guerra, así que no puede
    depender de ella: quien tenga Discord en inglés verá `/create-war` aunque
    la guerra se juegue en español.
  - Todo lo que el bot **responde** va en el idioma de la guerra.
  Un jugador inglés en una guerra en español escribe `/train` y recibe el
  combate narrado en español. Es lo correcto: la partida es una sola y se
  cuenta en un idioma, pero cada quien escribe en el suyo.
- Un idioma que no tenemos (francés, por ejemplo) se queda con el nombre por
  defecto, que es el español. Nada se rompe por no traducirlo.

## Lo que se ve en la ficha

Fecha: 2026-11-07.

- **El Noble Fantasma se enseña con su rango**: "Excalibur (rango A)". El
  rango viene de los datos, como el nombre, y no se traduce.
- **El tipo se importa pero no se enseña.** "Anti-Fortress", "Anti-Army" y
  compañía solo los entiende quien conoce la serie, y una ficha no es sitio
  para presumir de datos. Se guardan igual, porque es por donde empezará cada
  Noble Fantasma a tener su propio efecto —un Anti-Army que pegue a varios se
  escribe solo—, y quitarlos obligaría a reimportar el plantel para
  recuperarlos.
- **Lo que hace se escribe con nuestras reglas, no con las de FGO.** El export
  trae un `detail` por Noble Fantasma ("restore your NP Gauge", "inflict Burn
  5 turns") y se descartó a propósito: describe un juego que no es este.
  Mentirle al jugador sobre lo que hace su Noble Fantasma es peor que no
  contarle nada. La ficha dice lo que de verdad pasa: ×3 de daño a un
  objetivo, el mana que cueste según su rasgo, y se puede repetir.
- **Las tres habilidades se ven desde el nivel 1**, las que todavía no tiene
  marcadas con un candado y con el nivel al que se abren. Saber lo que te
  viene es parte de decidir cuánto entrenas, y no hay nada que esconder.

## El tope de 4 y quién se queda fuera

Fecha: 2026-11-07.

- **Se sortea quién entra en la cadena**, no entran los primeros por orden de
  declaración. Esa era la propuesta vieja y abría un agujero: al que se queda
  fuera le tocaba descansar, descansar no arriesga nada, y entonces declarar
  tarde era la mejor jugada del día. Medido con guerras enteras, al mismo
  jugador le cambiaba la tasa de victorias del 10% al 27% según si declaraba
  antes o después que los demás. Ahora quedarse fuera es suerte, no reloj.
- **Declarar un ataque es comprometerse a pelear.** Al que no cabe se le busca
  otro rival: primero un Master libre, y si no hay, otro atacante que tampoco
  cupo. Solo descansa si no queda nadie. Antes "redirigir o descansar" era
  decisión suya, que es la misma puerta por otro lado.
- Medido después del cambio, con 80 guerras por caso: una persona sola contra
  6 bots gana el 20% (le toca 14.3%), con 2 personas el 28.7% (28.6%), con 4
  el 61.3% (57.1%). Sigue en el margen de la muestra, y las guerras duran algo
  menos que antes, 8.7 días contra 9.0, porque ahora casi nadie descansa.
- Lo que sigue abierto es el otro lado del mismo problema: **no atacar nunca
  no cuesta nada**. Quien no declara solo pelea si alguien lo elige, y nadie
  gana nada por atacar más allá de eliminar rivales, así que se puede vivir a
  costa de que los demás se desgasten. Eso pide un premio por atacar o un
  coste por descansar, que es diseño nuevo (ver `puntos-abiertos.md`).

## Las guerras se guardan en SQLite

Fecha: 2026-11-07.

- **Una guerra sobrevive a un reinicio del bot.** `src/repositorio.py` la
  guarda y la carga; el Cog la lee al encenderse (`cog_load`) y la guarda al
  final de cada acción. Con esto el plazo ya vive en la tabla `plazos` y la
  regla de la casa se cumple.
- **Una guerra se guarda entera, de una vez.** `guardar()` reescribe sus 7
  Masters y Servants en lugar de apuntar cambios campo a campo. Son 7 filas:
  cuesta nada y quita de encima el error más probable de todos, que es
  olvidarse de guardar un campo que cambió.
- **Se guarda desde los métodos compartidos**, los `texto_*` y `pelear_npc`,
  no desde cada comando y cada botón. Es la misma razón por la que esos
  métodos existen: el comando y el botón llaman al mismo sitio, así que las
  dos puertas no se pueden desincronizar. Son 7 llamadas en vez de 15.
- **Un Servant se guarda por `collection_no`, no por nombre.** Los nombres no
  son únicos (dos Cú Chulainn, tres Medusa) y el plantel se regenera. Si al
  cargar el personaje ya no está en el catálogo, **esa guerra no se carga** y
  se registra el aviso: es mejor perderla que resucitarla con otro personaje
  dentro. Y un dato raro no impide arrancar el bot.
- `sin_repartir` y `orden_declaraciones` se guardan como listas JSON en dos
  columnas de `guerras`. Son listas ordenadas que pertenecen a la guerra, sin
  identidad propia y que nadie consulta por separado; una tabla para cada una
  sería ceremonia sin uso.
- **Las columnas nuevas se añaden al arrancar** si faltan (`migrar()`), en vez
  de obligar a borrar un `graal.db` que ya exista.
- Una guerra terminada se marca con `terminada_en` y deja de cargarse, pero no
  se borra: sirve para saber quién ganó cada una.
- Si guardar falla, se registra y la partida sigue: la guerra está viva en
  memoria y el jugador ve su resultado. Perder el guardado es malo; cortarle
  la jugada por eso es peor.
- Lo que no se guarda a propósito: nada de las batallas. Hoy se pelean enteras
  dentro de `cerrar_dia()` y duran un instante. Cuando existan las batallas por
  turnos, que duran días, tendrán que guardarse con las tablas `batallas`,
  `participantes` y `decisiones`, que ya están en el esquema.

### Tres errores que encontró la persistencia

Ninguno de los dos se veía jugando, y los dos eran de la lógica del juego:

- **Un lobby con una sola persona se daba por terminado.** `Guerra.terminada`
  era `fase is TERMINADA or len(activos) <= 1`, y en un lobby recién abierto
  efectivamente solo hay uno "en pie". La persistencia lo marcaba como acabado
  en cuanto se creaba y no lo volvía a cargar. Ahora pide además `dia >= 1`.
- **Y tenía ganador antes de empezar.** `ganador()` devolvía el único activo
  sin comprobar que la guerra hubiera acabado.
- **Al terminar una guerra, su canal se quedaba bloqueado** hasta reiniciar el
  bot: `/crear-guerra` miraba si el canal tenía guerra, y una terminada sigue
  en memoria. Lo delató la asimetría con la base de datos, que no vuelve a
  cargar las terminadas: el mismo canal estaba libre o no según si habías
  reiniciado. Ahora una guerra terminada no estorba, pero se queda en memoria
  para que `/estado-guerra` siga contando cómo acabó.

Los dos estaban tapados porque las otras puertas comprueban la fase antes. Es
un buen argumento para persistir temprano: obliga a mirar el estado desde
fuera, y ahí se ven cosas que desde dentro no.

## El vigilante de plazos

Fecha: 2026-11-07.

- **Cuando se agota la ventana de preparación, el día se cierra solo.** Con eso
  una guerra avanza sin que nadie la empuje, y una persona que no aparece deja
  de bloquearla: el botón del creador espera a que todos acaben su día, el
  plazo no espera a nadie. Y no le quita nada a nadie, porque quien no entrenó
  tuvo la ventana entera.
- **Quién decide que un día venció es la `Guerra`**, con `plazo_cumplido` y su
  propio `reloj`. El módulo `src/vigilante.py` solo pone el despertador y
  habla por el canal, que es lo único que necesita a Discord. Así el plazo se
  prueba con un reloj de mentira y las 24 horas pasan en una línea.
- **El plazo lo pone `abrir_dia`**, como todo lo demás del día. Si lo pusiera
  quien abre el día desde fuera, un día podría quedarse sin plazo y la guerra
  se pararía para siempre esperando a alguien. Es la tercera vez que esa
  decisión se toma igual, y por la misma razón.
- Revisa cada 30 segundos. La ventana más corta son 30 minutos, así que el día
  se cierra con un retraso que nadie nota y el bot no hace nada el 99% del
  tiempo.
- Si al cerrar un día algo falla, se registra y se sigue con las demás: una
  guerra rota no puede congelar a todas las del servidor. Si el canal ya no
  existe, **no** cierra el día: cerrarlo sin poder contarlo es peor, porque
  nadie sabría qué pasó y no habría registro que mirar.
- `/estado-guerra` dice lo que queda de preparación, redondeado hacia arriba,
  porque un "0 min" que todavía no ha vencido miente.

### Lo que todavía no cumple la regla de la casa

La regla dice que **los plazos van en la base de datos, nunca en memoria**, y
este vive en memoria con la guerra. Es a sabiendas: no tiene sentido guardar el
plazo de una guerra que no se guarda, y hoy `commands.py` tiene las guerras en
un diccionario, así que un reinicio se las lleva por delante. Guardar filas en
`plazos` que apuntan a guerras inexistentes sería peor que no guardarlas,
porque parecería hecho.

El orden correcto es: primero persistir las guerras, y entonces el plazo se
guarda con ellas y al arrancar se revisa `db.plazos_vencidos()`. El esquema ya
está en `src/db.py` esperando. Está anotado en `puntos-abiertos.md` y en la
cabecera de `src/vigilante.py`, que es donde lo va a buscar quien lo retome.

## El creador puede cerrar el día cuando quiera

Fecha: 2026-11-07.

- **La ventana de preparación es el plazo máximo, no el mínimo.** Quien abrió
  la guerra cierra el día con `/empezar-batallas` o con el botón rojo de su
  menú. Para una guerra entre amigos o de prácticas contra bots, esperar una
  hora cuando ya está todo el mundo no aporta nada.
- **El cierre vive en `src/game/dia.py`, no en `commands.py`.** `cerrar_dia()`
  invoca por quien falte, forma las batallas, las pelea, registra las derrotas
  y llama a `siguiente_dia()`, que abre el siguiente. Es la misma razón que
  `abrir_dia`: el día se cierra en un solo sitio, porque lo van a llamar dos
  puertas distintas (este botón y el vigilante de plazos) y dos guerras
  iguales tienen que acabar igual.
- Devuelve un `CierreDelDia` con datos, no con frases: quién fue invocado, qué
  batallas hubo, quién cayó, quién descansa y cómo acabó. La capa de Discord
  solo lo narra, así que el vigilante de plazos podrá reusarlo tal cual.
- **Las batallas las juega la IA, por ahora.** El combate por turnos está hecho
  y probado en `battle.py`, pero su capa de Discord no existe. Hasta que
  exista, cerrar el día las resuelve con la misma IA del simulador y publica
  el registro; el mensaje lo dice en cursiva, para que nadie crea que se perdió
  su turno. Cuando se construya la capa de turnos, lo que cambia es `dia.py`.
- Con esto **una guerra ya se puede jugar de punta a punta en Discord**, que
  antes no se podía: días, eliminaciones, ganador y Grial. Hay una prueba que
  cierra días hasta que queda uno solo.
- El botón no se les enseña a los demás, en vez de enseñárselo apagado: un
  botón apagado parece algo que te falta.
- **Medido, y abre un agujero en las guerras con varias personas.** 1500
  guerras de 4 personas, el caso peor: el creador entrena sus 4 combates y
  cierra el día enseguida, todos los días.

  | | gana una persona | h0 (creador) | h1 | h2 | h3 |
  |---|---|---|---|---|---|
  | todos entrenan | 58.7% | 11.5% | 16.9% | 14.5% | 15.9% |
  | h0 cierra antes de que entrenen | 31.2% | **22.9%** | 2.6% | 2.9% | 2.9% |

  Al creador le dobla las victorias y a los otros tres les deja en un sexto de
  lo que tenían. Y hasta ganan los bots más, porque tres humanos sin entrenar
  son presa fácil. **A los bots no les afecta**, porque entrenan al abrirse el
  día, no al cerrarse: en una guerra de prácticas de una persona contra 6 bots
  el botón no da ninguna ventaja, solo comodidad.

- **Cerrado con el botón de listo**, que es la fase `LISTOS` que ya estaba en
  las reglas. `puede_cerrar` exige que todas las personas vivas hayan dicho que
  acabaron su día, y mientras no entrenen no lo van a decir, así que el botón
  pasa a significar "ya está todo el mundo" en vez de "me adelanto".
  - Cada quien lo dice con "Ya acabé mi día" en su menú, y se anuncia en el
    canal, para que se vea por quién se espera.
  - **Decirlo cierra tu día de verdad**: después ya no puedes entrenar. Si
    pudieras, decirlo no significaría nada y el agujero seguiría abierto.
  - El creador **no se espera a sí mismo**: pulsar "empezar las batallas" ya
    es decir que acabó. Si no, su propio botón nacería apagado y no habría
    forma de encenderlo.
  - Los bots están listos desde que abren el día, así que nunca hacen esperar:
    una guerra de prácticas contra bots se cierra igual de rápido que antes.
  - Un eliminado tampoco hace esperar.
  - `cerrar_dia()` **no** comprueba nada de esto: la condición está solo en
    `puede_cerrar`, que es la puerta del creador. El vigilante de plazos tendrá
    que cerrar el día aunque falte gente por responder, que es justo para lo
    que existe.
- Comprobado con 300 guerras: intentando el abuso (entrenar, marcar listo y
  pulsar el botón sin que los otros tres digan nada) el día no se cierra
  ninguna vez. Y vuelto a medir el reparto con todos listos, que es el camino
  normal, sale idéntico al de antes del arreglo (11.5% / 16.9% / 14.5% /
  15.9%): no cambia la guerra, solo cierra la puerta.
- Ojo al leer la tabla de arriba: la segunda fila sigue siendo lo que hace
  `cerrar_dia()` si se le llama sin preguntar, porque el que no comprueba nada
  es él. Eso ya no se puede provocar con el botón, y por el lado del vigilante
  de plazos no es un abuso: si el día se cierra porque se agotó la ventana,
  quien no entrenó tuvo la ventana entera para hacerlo.

## La invocación la pide cada Master

Fecha: 2026-11-07.

- **El sorteo y el reparto se separan.** Al empezar la guerra se sortean los 7
  Servants (los cupos de clase y la tirada del Ruler) y quedan en
  `Guerra.sin_repartir`; cada Master pide el suyo con `invocar_para()` cuando
  quiera, a lo largo del día 1.
- El sorteo tiene que seguir siendo de la guerra entera y no de cada Master.
  Los 7 cupos de clase y el Ruler que desplaza a uno son una propiedad de la
  mesa: si cada uno sorteara el suyo por separado saldrían clases repetidas y
  el triángulo dejaría de significar nada.
- **Lo que te toca sale al azar de lo que queda**, aunque la lista ya venga
  mezclada del sorteo. Es a propósito: si fuera por orden de llegada, invocar
  primero sería una jugada, y la invocación no debería ser una jugada. Así el
  momento que eliges no cambia lo que recibes.
- **El plazo vive en `formar_batallas`, no en `siguiente_dia`.** Lo primero que
  hace es invocar por los que falten. Es la tercera vez que aparece la misma
  puerta: no declarar, declarar tarde y ahora no invocar eran formas de no
  pelear sin pagar nada. Si el plazo estuviera en `siguiente_dia` correría
  *después* de las batallas, y esperar sería un día de inmunidad gratis.
- Mientras no invocas no puedes entrenar ni declarar un ataque, pero **sí te
  pueden atacar**: para cuando se forman las batallas ya tienes Servant. Por
  eso `declarar_ataque` exige Servant al atacante y no al objetivo.
- Los bots invocan al abrir el día, dentro de `abrir_dia`. Elegir el momento es
  una decisión de jugador y para la IA no hay nada que decidir.
- Medido con 600 guerras por caso, igual que antes del cambio: una persona sola
  contra 6 bots gana el 16.7% (le toca 14.3%), con 2 el 27.7% (28.6%), con 4 el
  59.8% (57.1%). La invocación a petición no mueve la mesa.
- **Y medido que esperar no conviene**, que era el riesgo de dar a elegir el
  momento. 3000 guerras de 4 personas, todas jugadas por la IA:

  | | gana una persona | h0 | h1 | h2 | h3 |
  |---|---|---|---|---|---|
  | todos invocan ya | 58.6% | 13.5% | 15.6% | 14.0% | 15.5% |
  | h0 espera el día 1 | 53.7% | **8.0%** | 14.6% | 15.7% | 15.5% |

  Con todos invocando enseguida los cuatro ganan lo mismo. Al que espera un
  día le cuesta casi la mitad de sus victorias, y a los otros tres no les
  cambia nada: el precio lo paga él solo, y son los 4 combates de
  entrenamiento que no peleó. Así que elegir el momento es sabor, no una
  jugada, que es lo que se buscaba.

## El menú de combate: la guerra ya se puede jugar

Fecha: 2026-11-07. Era el último hueco grande: el motor de turnos estaba hecho
y probado desde el principio (`src/game/battle.py`) pero no había forma de
usarlo, así que `cerrar_dia()` peleaba las batallas con la IA en todos los
lados y el jugador solo leía el resultado.

### Lo que faltaba no era el combate, era esperar

`battle.py` sabe resolver un turno cuando tiene todas las decisiones. Lo que
no sabía nadie es **esperar a que lleguen**. Eso es `src/game/combate.py`, y es
lógica pura, sin Discord, como todo lo de `game/`:

- `pendientes` es a quién se espera ahora mismo,
- `decidir` apunta una decisión y devuelve `[]` mientras falte alguien,
- el último que decide cierra el turno y se lleva los eventos,
- `avanzar_con_ia()` es el plazo: rellena por quien no contestó y sigue.

**Las decisiones de un turno son simultáneas y secretas**, y de ahí sale toda
la forma del objeto. Nadie ve lo que eligió otro; el turno no se resuelve a
medias; y los bots deciden en el mismo instante que las personas, no antes,
porque si decidieran antes el orden de llegada valdría información. Por lo
mismo, elegir no se puede cambiar: nadie vería nada, pero el menú apaga los
botones al elegir y la regla tiene que estar también en el motor.

Un combate **sin personas vivas dentro** se juega solo hasta el final: dos
bots, o la última persona caída. Así el camino viejo —la IA por todos— es un
caso particular de este y no un módulo aparte, y una guerra de bots se
comporta exactamente igual que antes.

### El día se cierra en dos mitades

Antes, cerrar el día era una cosa. Ahora son dos y las dos viven en `dia.py`:

1. `abrir_combates()` acaba la preparación: invoca por quien falte, forma los
   grupos y deja las batallas **en curso** (`Fase.BATALLA`). Las de puros bots
   salen ya resueltas.
2. `cerrar_combates()` pasa al día siguiente, y lo llama **la última decisión
   de la última batalla**, no un comando.

`cerrar_dia()` sigue existiendo y hace las dos cosas de corrido con la IA: lo
usa el simulador, lo usa una guerra sin personas en ninguna batalla, y es la
red de seguridad. Las dos formas tienen que dejar la misma mesa, y hay una
prueba que lo exige (`test_jugar_a_mano_deja_la_misma_mesa_que_la_ia`).

Lo que no se puede olvidar —apuntar quién vio qué Servant y registrar la
derrota— está en un solo sitio, `anotar_batalla()`, que llaman los dos
caminos. `recoger()` es idempotente a propósito, porque lo llama cada
decisión: si una batalla se anotara dos veces, una derrota contaría doble.

### El menú, y lo que el canal no puede decir

El canal recibe un aviso y un botón "Abrir mi combate"; lo que se ve al
pulsarlo es privado, igual que el resto del juego. **Dentro de una batalla sí
se ven los Servants de los rivales**: estar delante de alguien es justo lo que
los destapa, así que no es una filtración sino la regla al derecho.

Los botones son atacar, defenderse, habilidad y Noble Fantasma, y se apagan
solos cuando no se pueden usar (sin mana, sin habilidad lista, un Servant que
no sabe defenderse). Igual que con planear el ataque, el motivo lo decide un
solo método del Cog (`motivo_para_no_decidir`) que usan tanto el botón para
apagarse como la acción para explicarse: si miraran cosas distintas, uno de
los dos miente. Las habilidades van en dos desplegables, cuál y sobre quién,
porque los objetivos dependen de la habilidad: una que va "a otro" no se puede
usar sobre uno mismo.

Cuando cae alguien y quedan dos o más en pie se abre la votación, y entonces
los botones de pelear se quitan y salen "Sigo peleando" y "Me retiro". No se
enseñan juntos a propósito: una votación no es un turno.

**El menú se refresca para todos cuando el turno se resuelve.** Al canal no se
puede mandar: las frases del registro nombran las habilidades, y el nombre de
una habilidad delata al Servant. Es la misma razón por la que el registro de
una batalla nunca fue público. Así que se le habla a cada uno en privado,
reusando su última interacción. Esto fue lo que falló al jugarlo por primera
vez con dos personas; está contado al final, en *Repartir el turno entre los
que pelean*.

### Los 5 minutos por turno

`Combate.plazo_cumplido()` los mide con el reloj de la guerra, y el vigilante
decide por quien no contestó. Sin esto, una persona que cierra Discord deja
parada la batalla, con ella el día y con él la guerra entera. Decidir por
alguien no es castigarlo: la IA elige por él lo mismo que elegiría por un bot.
El reloj se pone a cero **en cada turno**, no en cada decisión: son 5 minutos
por turno, no por persona.

### Una batalla en curso vive en memoria, y es a propósito

Los plazos van a la base de datos porque una guerra dura días. Una batalla
dura minutos, así que los combates en curso viven en `self.combates` del Cog y
un reinicio del bot los pierde. Lo que **no** se puede perder es la guerra, y
ahí estaba la trampa: se quedaba en `Fase.BATALLA` esperando una decisión que
ya no iba a llegar.

Lo que lo salva es que sí sobrevive **quién peleó hoy**: `anotar_batalla` deja
`ultimo_registro_dia` puesto y eso se guarda. Así `dia.recuperar_dia()` vuelve
a formar los grupos, pelea con la IA solo los de quien no peleó todavía y
cierra el día; el que ya tiene su batalla apuntada no la repite. Lo llama el
vigilante, que es quien puede contarlo en el canal.

Guardar las batallas de verdad sigue pendiente (las tablas están en el
esquema), y ahora por fin tiene sentido hacerlo.

### Dos arreglos de la primera partida de verdad

**En un duelo no se pregunta a quién golpear.** Si solo queda un rival en pie,
elegirlo no es una decisión: es un clic de más. El desplegable sale cuando hay
dos o más. Lo mismo con una habilidad que solo puede ir a un sitio (a uno
mismo, o al único rival). La de "qué habilidad" sí se pregunta siempre aunque
haya una sola, porque es lo único que dice qué hace: comprometer el turno a
ciegas sería peor que el clic.

**Cada Servant que cae paga su derrota, no solo el primero.** `anotar_batalla`
apuntaba `caidos[0]` y nada más. La batalla se acaba cuando cae uno, así que
casi siempre es el único; pero si quedan dos o más en pie y alguien vota por
seguir, se sigue, y el que cayera después **salía gratis**. `BatallaDelDia`
pasó a llevar `caidos` y `eliminados` en plural y el canal cuenta una línea
por cada uno.

El mismo error estaba en el simulador (`_jugar_batalla_de_guerra` devolvía uno
solo), así que **todas las medidas de justicia se habían hecho con derrotas de
menos**. Y no era un detalle: midiendo 12 000 batallas después del arreglo,
**todas acaban con un solo Servant en pie**, el 100% de las veces, porque la
batalla sigue si alguien vota por seguir y el que va ganando siempre vota
seguir. Así que un grupo de 4 deja 3 derrotas y no 1, y una guerra pasa de 8.7
días a **3.9**.

La mesa sigue siendo justa (14.0% para una persona contra 6 bots, 56.8% con
cuatro, con 5 semillas x 200 guerras), pero la guerra es otra: el nivel máximo
que se alcanza baja a ~12 y la tercera habilidad, la del nivel 15, no llega
nunca. Eso es una decisión de diseño pendiente, no un error, y está en
`puntos-abiertos.md` con las opciones y lo que cuesta medirlas.

### Las puertas por las que se cierra el día siguen siendo las mismas

Eran tres (`/empezar-batallas`, el botón rojo del menú y el vigilante) y lo
que tenían que dejar igual era el botón del canal. Ahora hay tres botones
posibles —el del combate, el del día nuevo o ninguno si la guerra acabó— así
que eso se sacó a un solo método, `aviso_y_vista_de_despues()`, y las tres
puertas lo llaman. Era el error que tuvo el botón rojo en su día; esta vez la
decisión vive en un sitio desde el principio.

## Nadie sabe que Servant lleva nadie hasta que pelea con el

Fecha: 2026-11-07.

- **Tu Servant es informacion tuya.** Al empezar la guerra el canal no dice
  quien lleva que, y cuando alguien invoca solo se anuncia que ha invocado.
  Cada Master guarda en `conocidos` a quienes ha visto en una batalla, y
  `Master.conoce(id)` es lo unico que decide si le ves la ficha. El tuyo
  siempre lo ves: `conoce` devuelve `True` para tu propio id.
- Lo que se gana es que **declarar un ataque es una apuesta**. El triangulo de
  clases decide buena parte del combate, asi que atacar a quien no conoces es
  elegir a ciegas; y una vez peleas con alguien, lo que aprendiste vale para
  todos los dias siguientes. Era la peticion: "los ataques se deben pensar de
  mayor manera".
- **Por eso `/estado-guerra` es privado** (`ephemeral`). No es una preferencia
  de presentacion: el estado ya no es el mismo para todos, asi que no puede ser
  un mensaje del canal. `texto_estado(guerra, quien=None)` revela cero por
  omision, para que un sitio nuevo que lo llame sin pasar `quien` filtre de
  menos y no de mas. Quien mira sin jugar no ve ningun Servant.
- Lo que si es publico de cada uno: su nombre, sus derrotas y sus sellos. Hacen
  falta para saber como va la guerra y no dicen que Servant es.
- **El registro de la batalla tuvo que volverse privado tambien**, y esto no
  estaba previsto. El canal publicaba el detalle turno a turno, y las frases
  nombran las habilidades y el Noble Fantasma: leer "Throne of Quirinus EX" es
  saber que ese es Romulus. Ocultar la ficha y publicar el registro no habria
  ocultado nada. Ahora el canal dice quien peleo contra quien y quien cayo, y
  el detalle se lo queda cada participante en `Master.ultimo_registro`, que ve
  desde su menu.
- Se guarda en la base de datos (`masters.conocidos`, una columna JSON). Si se
  olvidara al reiniciar, volverias a no saber contra quien peleaste, que es
  justo lo que el jugador ya se gano.
- Esto no toca el balance: lo que cambia es quien ve que, no como pelean. La IA
  siempre decidio con lo que tiene delante en la batalla, no con la ficha de
  los demas, asi que no juega con ventaja. Pendiente en
  `docs/puntos-abiertos.md`: la IA tampoco aprovecha lo que conoce al declarar.

## Planear el ataque desde el menu, y el menu que vuelve cada dia

Fecha: 2026-11-07.

- **Declarar un ataque ya es una accion del jugador.** Hasta ahora solo los
  bots declaraban (`declarar_ataque_de_bot`): una persona dejaba su objetivo
  vacio y `formar_batallas` le buscaba rival. Ahora hay un boton "Planear
  ataque" en el menu que abre un desplegable con los rivales vivos.
- **El desplegable es el sitio donde el secreto del Servant sirve para algo.**
  De quien no hayas peleado dice "Servant desconocido" y sus derrotas; de quien
  si, el Servant, su nivel y su clase. Eliges a ciegas la primera vez, y el
  triangulo de clases decide buena parte del combate. Las opciones las arma
  `opciones_de_ataque` en el Cog y no la vista, porque la regla de quien ve que
  ya vive en `Master.conoce` y no puede estar en dos sitios.
- **A quien atacas no se anuncia nunca.** Ni en el canal ni al objetivo. Si se
  anunciara, el secreto no valdria nada: el rival sabria con quien va a pelear
  y deduciria por eliminacion. El unico sitio donde se ve es la etiqueta del
  propio boton, que pasa a decir "Atacas a X" para que no se te olvide.
- **Se puede cambiar de objetivo hasta que se cierre el dia**, porque el orden
  de declaracion no decide nada desde que `formar_batallas` sortea quien entra
  en una cadena de mas de 4. Si alguna vez volviera a importar el orden, esto
  habria que repensarlo.
- **Estar listo tambien cierra el ataque**, igual que cierra el entrenamiento.
  Es la misma razon: si decir "ya acabe mi dia" te dejara seguir cambiando de
  objetivo, decirlo no significaria nada, y el creador podria cerrar el dia
  mirando lo que han hecho los demas. El motivo lo decide
  `motivo_para_no_planear` en el Cog, y lo usan el boton (para apagarse) y la
  accion (para explicarse): asi no pueden decir cosas distintas.
- Declarar **no** garantiza pelear contra ese rival: si la cadena pasa de 4,
  `formar_batallas` sortea quien entra y al que no cabe le busca otro. Es de
  antes y esta medido (ver "El tope de 4 y quien se queda fuera"), pero ahora
  se nota mas, porque antes nadie habia elegido nada.

**El menu vuelve al canal cada dia.** Al cerrarse un dia, el boton publico
"Abrir mi menu" se manda otra vez. Antes solo lo hacian dos de las tres
puertas por las que se cierra un dia: `_contar_cierre` (el comando
`/empezar-batallas`) y el vigilante de plazos. Faltaba la tercera, el boton
rojo del propio menu, asi que quien cerraba el dia desde ahi dejaba al canal
con el boton del dia anterior. No es cosmetico: el menu de ayer sigue
respondiendo, pero sus botones se armaron con el estado de ayer, y al dia
nuevo todos tienen entrenamientos otra vez, un ataque que planear y un listo
que decir. Es la tercera vez en este proyecto que una regla se escribe en
varios sitios y uno se queda atras; si aparece una cuarta puerta, lo que
corresponde es sacar "cerrar el dia y contarlo" a un solo metodo.

## El Noble Fantasma se puede repetir

Fecha: 2026-11-07. Viene de "El efecto MANA no paga el turno que cuesta", en
`puntos-abiertos.md`, que ahora queda resuelto.

**Se quitó el tope de uno por combate.** Ahora se lanza cada vez que se junten
los 100 de mana (el que diga el rasgo), y cada uno los gasta otra vez. En
código son cuatro líneas: `Combatiente.nps_usados` cuenta en vez de prohibir,
`puede_noble_fantasma` solo mira el mana, y la IA deja de dar el mana por
perdido después del primero.

**El problema que arregla.** Con el tope, el mana no era un recurso escaso
sino un reloj: con 20 inicial y 15 por ataque, *todo el mundo* llegaba a 100
en el turno 6 de un combate de 10, así que el Noble Fantasma salía igual
hicieras lo que hicieras, y el mana que pasaba de 100 se tiraba entero. Una
habilidad de mana solo adelantaba algo que iba a pasar, a cambio de un turno
sin atacar. Medido: Semiramis con su *Familiar (Dove) D* (+60 de mana)
adelantaba su Noble Fantasma del turno 6 al 3 y **perdía 23 puntos** de
victorias contra ella misma sin esa habilidad.

### Lo que se midió

Cada efecto a solas (un personaje con **una** habilidad de ese efecto contra
el mismo sin ninguna), nivel 5, 30 personajes x 200 combates. El "antes" se
reconstruyó volviendo a poner el tope **y** la guarda de la IA: con el tope
puesto y la IA nueva salía un 2% que no era el de antes, porque la IA gastaba
turnos en mana que ya no podía usar.

| efecto | antes | ahora |
|---|---|---|
| curar | 71.6% | 57.5% |
| ataque | 69.1% | 65.5% |
| defensa | 44.8% | 64.6% |
| crítico | 42.0% | 42.8% |
| **mana** | **23.9%** | **68.2%** |
| *rango* | *47.7 puntos* | *25.4 puntos* |

Los cinco efectos pasaron de abrirse 48 puntos a abrirse 25. El mana deja de
ser una trampa y la defensa también sube, porque ahora hay golpes grandes de
los que defenderse. La curación baja por lo mismo: un 12% de la vida tapa
menos cuando el daño que entra es mayor.

Y el plantel entero a nivel 15 mejora: la desviación baja del 18.1% al 17.5%
y los personajes fuera de la banda 35-65% pasan de **166 a 141**. Son 25
personajes que estaban rotos y ya no lo están, de los 147 que llevan alguna
habilidad de mana.

**La mesa sigue siendo justa.** Una persona contra 6 bots, jugados todos por
la misma IA, gana el **14.1%** sobre 3000 guerras, y le toca el 14.3%.

### El ruido de la medida de justicia, que casi me engaña

La primera corrida después del cambio dio 12.8% con la semilla 7, contra el
16.7% de antes: parecía que el cambio había perjudicado a la persona sola. No
era verdad. Esa medida con `-n 600` tiene **±2.7 puntos de desviación entre
semillas** (11.8%, 12.5%, 12.8%, 14.7%, 18.5%), así que un solo número a 600
guerras no distingue nada de nada. **Para esta medida hacen falta varias
semillas, no una corrida más larga.** Esto también explica los números raros
que había apuntados antes (5.0% con `-n 60`, 15.8% y 16.7% con `-n 600`).

### Lo que no se tocó, y por qué

`VALOR_POR_EFECTO[MANA]` se queda en 60 aunque el mana quede ahora el más alto
de los cinco (68.2% contra el 65.5% del ataque). No se puede afinar más fino:
la IA solo usa una habilidad que devuelva más de un ataque, y con la cuenta de
`_cuanto_paga` eso es exactamente 55 de mana. Por debajo de 55 no la usa nunca
y el efecto vuelve a ser letra muerta (51.4% con 55, que es "no la usa"); por
encima, el valor sube a saltos porque el mana está cuantizado por turnos
(60 → 68.2%, 70 → 62.6%, 80 → 63.5%, 100 → 71.9%). Entre un efecto muerto y
uno tres puntos por encima del ataque, lo segundo.

### Efectos secundarios, medidos y sin resolver

- **El entrenamiento se volvió más fácil.** Contra el NPC 4: nivel 10 del
  85.8% al 95.2%, nivel 15 del 81.8% al 93.0%. Los factores de dificultad
  (0.55, 0.68, 0.80, 0.92) estaban calibrados contra el combate viejo.
  Resuelto el mismo día: ver "Los NPC se endurecen y dejan de ser un
  acantilado".

  Aquí escribí primero que la causa era que *las Sombras no tienen Noble
  Fantasma y el jugador ahora repite el suyo*. **Es falso y conviene que
  quede escrito, porque es un error fácil de repetir**: `SIN_NOBLE_FANTASMA`
  solo le quita el nombre en la ficha. `puede_noble_fantasma` mira el mana y
  nada más, así que una Sombra lanza Noble Fantasmas igual —medido, en 40
  combates del día 5 la Sombra soltó 74 y el jugador 52—. La causa real es
  otra: **repetir el Noble Fantasma amplifica cualquier ventaja de
  estadísticas**, porque multiplica por 3 un ataque que ya era mayor. Es el
  mismo motivo por el que un nivel de diferencia pasó a pesar más.
- **El nivel pesa un poco más**: un nivel de diferencia pasa del 76.4% al
  80.4%, dos del 82.6% al 87.2%. Se refuerza con lo anterior, porque entrenar
  es más rentable.
- **El crítico es ahora el efecto más flojo** (42.8%), y no es culpa de este
  cambio: antes estaba en el 42.0%. Estaba tapado por el del mana.

Los tres están en `puntos-abiertos.md`.

## Los NPC se endurecen y dejan de ser un acantilado

Fecha: 2026-11-07. Viene de "El Noble Fantasma se puede repetir", que dejó el
entrenamiento demasiado fácil.

**Lo que había no era fácil, estaba roto.** Midiendo día a día en vez de solo
el día 1 (40 personajes, nivel 10):

| día | NPC 1 | NPC 2 | NPC 3 | NPC 4 | XP/día |
|---|---|---|---|---|---|
| 1 | 100% | 100% | 99% | 92% | 159 |
| 3 | 100% | 100% | 99% | 84% | 153 |
| 5 | 100% | 100% | 95% | **14%** | 103 |
| 7 | 100% | 100% | 90% | **5%** | 94 |

Los tres primeros eran gratis siempre y el cuarto se volvía imposible entre el
día 3 y el 5. Eso **no lo causó el Noble Fantasma repetible**: ya estaba, y
llevaba ahí desde que se calibraron los factores. No se vio porque el modo
`npc` del simulador medía un solo personaje y un solo día, que son justo las
dos dimensiones donde se rompía. Ahora recorre los días 1, 3, 5 y 7 con una
muestra del plantel.

### El factor de dificultad es un dial horrible

Victorias del jugador contra una Sombra de factor f, medido a los niveles 1,
5, 10 y 15 (40 personajes x 25 combates, sin endurecimiento):

| factor | 0.80 | 0.85 | 0.88 | 0.92 | 0.95 | 0.97 | **1.00** | 1.03 |
|---|---|---|---|---|---|---|---|---|
| victorias | 100% | 98% | 96% | 92% | 87% | 83% | **49%** | 14% |

Todo lo que baje de 0.85 es un regalo, todo lo que pase de 1.00 es imposible,
y **los últimos tres centésimos valen 34 puntos**. La banda útil es 0.85-1.00
y dentro de ella la curva es un escalón. Es la razón por la que el acantilado
existía: el 3% de endurecimiento por día empujaba el 0.92 del 4.º NPC a 1.03
en el día 5, y ahí ya no hay partido.

La buena noticia es que **la curva no depende del nivel** (la misma tasa a
nivel 1 y a nivel 15, ±3 puntos), así que la escalera significa lo mismo
durante toda la guerra. Eso es lo que permite elegir los factores leyendo esta
tabla en vez de probar a ciegas.

### Lo que quedó

- `FACTOR_DIFICULTAD = (0.88, 0.93, 0.96, 0.985)`, dentro de la banda útil.
- `ENDURECIMIENTO_POR_DIA = 0.01`, antes 0.03.
- `FACTOR_MAXIMO = 0.99`, **nuevo**, y es lo que mata el acantilado: **una
  Sombra nunca puede ser un espejo más fuerte que tú.**

| día | NPC 1 | NPC 2 | NPC 3 | NPC 4 | XP/día |
|---|---|---|---|---|---|
| 1 | 97% | 90% | 85% | 75% | ~139 |
| 3 | 95% | 88% | 82% | 71% | ~131 |
| 5 | 94% | 83% | 71% | 69% | ~124 |
| 7 | 91% | 80% | 70% | 68% | ~122 |

Los cuatro se pueden ganar siempre y ninguno es gratis. La XP baja de ~139 a
~122, así que entrenar sigue rindiendo más al principio; antes bajaba de 159 a
94, pero esa caída venía entera del acantilado. Con ~130 de media, llegar al
nivel 15 son unos 6 días, que entonces eran 6 de los 8.8 que duraba una
guerra. (Desde que todas las derrotas cuentan una guerra dura 3.9 días, así
que al nivel 15 no se llega: ver "La votación nunca para una batalla" en
`puntos-abiertos.md`.)

### Que entrenar los cuatro siga conviniendo, que era el riesgo

Endurecer los NPC tiene un precio escondido: perder uno resta vida inicial en
la batalla contra jugadores (0.75 con una derrota, 0.50 con dos). Antes casi
no se perdía ninguno (0.09 derrotas esperadas al día); ahora se pierden 0.53 el
día 1 y 0.91 el día 7. Si el 4.º NPC saliera a perder, la escalera sería
una trampa y el que entrena menos ganaría más: exactamente el error del mana,
otra vez.

Medido con 4 personas y 3 bots, donde h0 pelea `k` combates y los otros tres
los cuatro (150 guerras x 2 semillas por k):

| k | gana h0 |
|---|---|
| 0 | 0.0% |
| 2 | 4.7% |
| 3 | 11.7% |
| **4** | **14.3%** |

Monótono, y el 4 cae justo en el 14.3% que le toca. **Entrenar los cuatro
sigue siendo la jugada**, y no entrenar no es una opción: quien no pelea
ninguno no gana ninguna guerra. La vida que se pierde en los NPC se paga con
los niveles que se ganan.

**Y la mesa sigue justa**: una persona contra 6 bots gana el **14.0%** de
media sobre 3000 guerras (5 semillas x 600), con el 14.3% esperado. De paso,
la desviación entre semillas de esa medida bajó de ±2.7 a ±1.1 puntos: con los
NPC duros el nivel y el entrenamiento deciden más, y la suerte del combate
menos, así que el estimador se volvió más estable.

### Un error mío que vale la pena dejar escrito

Diagnostiqué primero que el entrenamiento se había abaratado porque *las
Sombras no tienen Noble Fantasma y el jugador ahora repite el suyo*. Es falso.
`SIN_NOBLE_FANTASMA` solo le quita el nombre en la ficha: `puede_noble_fantasma`
mira el mana y nada más, así que una Sombra los lanza igual —en 40 combates
del día 5 soltó 74 y el jugador 52—. La causa real es que **repetir el Noble
Fantasma amplifica cualquier ventaja de estadísticas**, porque multiplica por 3
un ataque que ya era mayor; es el mismo motivo por el que un nivel de
diferencia pasó a pesar más. Si alguna vez se quiere que una Sombra de verdad
no tenga Noble Fantasma, hay que **gatear la acción** en `battle.py`.

### Y `npc.py` ya tiene pruebas

No tenía ninguna. Las 16 nuevas no fijan tasas de victoria —eso es del
simulador y vive aquí— sino las reglas que, si se rompen, rompen el
entrenamiento sin que nada avise: que ninguna Sombra pase del tope ningún día,
que la escalera no se invierta al endurecerse, que un NPC no se ablande con
los días, y que el 4.º del día 7 no sea una pared.

## Jugar contra bots, y quién se lleva el Grial

Fecha: 2026-11-06.

- **Los cupos que no llena nadie los llena la IA.** Quien abrió la guerra usa
  `/empezar-guerra` y entran tantos bots como falten, así que se puede jugar
  solo contra 6 sin esperar a nadie. Hace falta al menos una persona: una
  guerra de siete bots no la miraría nadie.
- **El Grial solo se entrega con 4 personas de verdad o más.** Es la condición
  que separa jugar de practicar: con uno o dos humanos y el resto bots, ganar
  diría más de la IA que del jugador. Con menos de 4 la guerra se juega igual,
  se gana igual y se cuenta igual; lo único que no hay es premio. Y un bot que
  queda en pie nunca se lleva el Grial, aunque la guerra lo otorgue.
- Es el número lo que decide, no el modo: 4 personas y 3 bots entregan Grial.
  No hay dos tipos de guerra, hay una con una condición.
- Cuenta cuánta gente **juega** la guerra, no cuánta queda viva: que los otros
  tres humanos caigan el primer día no le quita el Grial al que aguanta. Si
  contara, convendría que tus rivales siguieran vivos, que es justo lo
  contrario de lo que pide el juego.
- **Los bots entrenan.** Pelean sus 4 combates NPC cada día, como un jugador
  aplicado. Si no lo hicieran se quedarían al nivel 1 y una guerra contra bots
  no tendría ninguna gracia a partir del día 2.
- **El día de los bots lo abre la guerra, no el bot de Discord.**
  `Guerra.abrir_dia()` entrena a los bots y declara sus ataques, y la llaman
  `empezar()` (el día 1) y `siguiente_dia()` (los demás). Durante un tiempo
  esas dos cosas existían pero solo las llamaba el simulador, así que en
  Discord los bots se quedaban al nivel 1: la guerra se jugaba a medias sin
  que nada fallara. Engancharlo a un comando habría sido peor, porque el día
  que el jugador no apareciera sus rivales no entrenarían, y una guerra de uno
  contra seis se ganaría sola. Al colgarlo del cambio de día no hay forma de
  que se olvide.
- Por eso la `Guerra` lleva su propio dado (`rng`): quien la crea puede pasarle
  uno con semilla, y el simulador lo hace para repetir una partida igual.
- Entrenan **antes** de declarar, y declaran todos juntos al abrir el día. Lo
  segundo da igual desde que `formar_batallas` sortea quién se queda fuera, y
  es lo que de verdad va a pasar en Discord: un bot no tiene por qué esperar.
  Medido después del cambio, con 600 guerras por caso: una persona sola contra
  6 bots gana el 15.8% (le toca 14.3%), con 2 personas el 27.2% (28.6%), con 4
  el 57.3% (57.1%), y el Grial sale en el 57% de las de 4 y en ninguna de las
  de 1 o 2. Con las 60 por defecto salía un 5% que no era más que la muestra:
  tres guerras de sesenta. Esta medida necesita `-n` grande.
- **Los bots siempre atacan**, y a quien atacan es al azar. Si descansaran,
  una guerra con pocos humanos no avanzaría nunca; y elegir bien a quién
  atacar es jugar por el jugador.
- Medido con `python -m src.simulator --semilla 7 guerras`, que juega guerras
  enteras con la IA en todos los lados, 80 por cada caso. La mesa sale justa:
  cada quien gana más o menos lo que le toca por reparto.

  | Personas | Gana una persona | Le toca | Entrega Grial | Días |
  | --- | --- | --- | --- | --- |
  | 1 | 12.5% | 14.3% | 0% | 9.0 |
  | 2 | 31.2% | 28.6% | 0% | 8.9 |
  | 4 | 58.8% | 57.1% | 59% | 9.1 |
  | 7 | 100% | 100% | 100% | 9.1 |

  Una persona sola contra 6 bots gana 1 de cada 8, que es lo que debe ganar
  jugando igual de bien; un jugador de verdad juega mejor que la IA, así que
  en la práctica le irá algo mejor. Y el Grial aparece exactamente donde debe:
  nunca con 1 o 2 personas, y en el 59% de las guerras de 4, que es cuando
  gana una de ellas.
- Esa medida costó dos intentos, y el error enseñó algo del juego: al
  principio los bots declaraban sus ataques todos juntos, antes o después de
  las personas, y la persona sola pasaba del 10% al 27% de victorias según el
  orden. No era el bot: es que **declarar tarde conviene**, porque cuando una
  cadena de ataques pasa de 4 Masters el que llega tarde se queda fuera y
  descansa. Ahora el simulador los intercala al azar, como llegarían de
  Discord, y la ventaja de declarar tarde quedó anotada en
  `puntos-abiertos.md` para decidirla aparte.

## Combates contra NPC

- Cada jugador elige cuántos combates NPC pelear, hasta 4, antes de la batalla contra jugadores.
- Dificultad creciente: el 1.º es el más fácil, el 4.º el más difícil; los NPC se hacen más fuertes cada día en juego.
- Perder un combate NPC consume el intento.
- Ganar da XP y objetos que ayudan; los combates NPC usan decisiones ocultas contra una IA simple.
- Penalización de vida inicial en la batalla de ese día: 1 derrota −25%, 2 −50%, 3 −75%, 4 −90%. Quien gana recupera toda la vida al terminar.

## Batalla contra jugadores

- Decisiones ocultas, daño aplicado por velocidad.
- El jugador elige a quién atacar; las batallas pueden ser de más de 2 jugadores, con un tope de 4. Si varios eligen al mismo jugador, entran todos en la misma batalla.
- Quienes quedan fuera de una batalla por el tope pueden redirigir su ataque contra un jugador libre o descansar; si los atacan, el combate se inicia igual.
- Si un ataque no conecta porque el objetivo ya cayó ante un ataque más rápido, solo se suma el mana y el ataque no se redirige.
- Botón de listo durante 5 minutos; si no lo pulsan, lucha la IA; debe aceptar al menos 1 jugador o el combate se aplaza.
- Máximo 5 minutos por turno para elegir acción. Si un Maestro no responde, el combate pasa a la IA, y puede volver a unirse mientras su rival elige su acción.
- Mana: cada Sirviente empieza con 20; atacar da 15; defender da 20.
- Defender: reduce 50% el daño y tiene 10% de no recibir daño; la segunda defensa seguida tiene 30% de éxito y, si falla, pierde el turno.
- Cada Sirviente tiene 3 habilidades (niveles 5, 10 y 15) que no gastan mana.
- Noble Fantasma único por Sirviente: cuesta 100 de mana y se puede lanzar como máximo 1 vez por combate.
- La batalla termina cuando un jugador es eliminado. Con 2 vivos en una batalla de 3, solo termina si ambos quieren; si uno quiere seguir, se juega un turno especial en el que quien sigue recibe el menú de acciones y quien quiso terminar solo espera. Después vuelven los turnos normales.

## Habilidades

Fecha: 2026-11-06.

- **Cada habilidad hace una sola cosa**, de una lista cerrada de cinco efectos
  propios: ataque, defensa, crítico, mana y curar. Son las perillas que el
  combate ya tenía. Una habilidad de FGO hace dos o tres cosas a la vez; se
  toma el primer efecto que sepamos traducir y el resto se pierde a propósito.
- El nombre y el efecto salen del importador y viven en los datos. El código
  solo tiene las perillas (`Efecto`, `Objetivo`) y los números, igual que con
  los rasgos: una habilidad nueva no puede inventar una regla.
- **Cuánto da cada efecto lo decide el juego, no el personaje.** Una habilidad
  de ataque es la misma para todos: el siguiente golpe pega x2.5. Igual la
  defensa (35% menos de daño durante 3 turnos), el crítico (+45 puntos durante
  3), el mana (+60) y la curación (12% de la vida). Las magnitudes de FGO se
  descartaron: están calibradas para un juego donde usar una habilidad no
  cuesta el turno, y traducirlas daba bonos que no pagaban. Se pierde variedad
  entre personajes a cambio de un combate que se puede explicar en una línea y
  balancear de verdad. Están en `VALOR_POR_EFECTO` y `TURNOS_POR_EFECTO`, en
  `personajes.py`, y una ficha escrita a mano puede traer su propio valor para
  un personaje que lo merezca.
- **Usar una habilidad da 10 de mana**, menos que atacar (15), que además hace
  daño. Sin esto, gastar el turno costaba el ataque *y* el mana, o sea
  retrasar el Noble Fantasma, y ninguna habilidad de ataque pagaba lo que
  cuesta: medido, el que las usaba ganaba el 44% de los duelos espejo.
- El bono de ataque multiplica también el Noble Fantasma, así que cargar el
  golpe y soltarlo al turno siguiente es la jugada más fuerte del combate. Es
  a propósito, y la IA la juega.
- **A quién se le da: lo decide el Maestro.** Las alianzas siguen siendo
  verbales, no mecánicas, pero un efecto que en FGO iba "a un aliado" o "a
  todo el bando" aquí se le puede dar a cualquiera de la batalla, incluido uno
  mismo, y el que iba "a otro" a cualquiera menos a uno mismo. Se descartó
  convertirlos en efectos sobre uno mismo: elegir es lo que vuelve jugables
  los pactos y las traiciones, y no costaba diseño nuevo. Lo que apuntaba a
  los enemigos queda fuera por ahora, porque los efectos negativos sí son
  diseño nuevo.
- **Una habilidad afecta a un solo objetivo.** Lo que en FGO iba a un grupo
  entero pasa a ir a uno elegido; no hay efectos en área.
- **El enfriamiento sale del efecto, no del personaje**: ataque y defensa 2,
  mana 3, crítico 5, curar 5. Un enfriamiento de N significa que la habilidad
  vuelve N turnos después, así que con 2 se usa en los turnos 1, 4 y 7 de un
  combate de 9. En FGO son 7 u 8 turnos, que aquí sería "una vez por combate".
  Un personaje puede traer su propio enfriamiento en la ficha, pero ninguno lo
  hace.
- **La duración no cuenta el turno en que se usa**, porque usarla ya gasta ese
  turno: si contara, una habilidad de 1 turno no serviría para nada.
- Si el objetivo elegido ya cayó, el efecto se pierde y la habilidad queda
  enfriando igual: la misma regla que el ataque y el Noble Fantasma, que no se
  redirigen.
- Usar una habilidad que todavía enfría pierde el turno, con aviso en el
  registro. No se corrige en silencio.
- Las Sombras de los combates NPC heredan las habilidades del jugador, como ya
  heredaban sus estadísticas. Si no, entrenar se volvería más fácil a partir
  del nivel 5 y la curva de XP se iría sola.
- Un retoque a mano en `personajes.json` que solo cambia el nombre de una
  habilidad **conserva el efecto** que trajo el importador: las habilidades se
  mezclan hueco por hueco, no en bloque. Por eso el orden importa, y hubo que
  reescribir los nombres a mano de los 8 personajes retocados para que cada
  uno sea la traducción de la habilidad que ocupa su hueco: antes "Instinto"
  estaba en el hueco del Carisma de Altria, y al pegarle el efecto quedaba un
  Instinto que subía el ataque de otro.
- La IA mide toda habilidad en la misma unidad, "ataques", porque usarla cuesta
  un turno de ataque, y solo usa lo que devuelve más de 1. No regala
  beneficios: una habilidad que solo sirve para otro es una decisión de
  Maestro, no de una heurística.

### Lo que se midió

La medida de referencia es `python -m src.simulator --semilla 7 habilidades`:
el mismo personaje de nivel 15 con sus habilidades contra sí mismo sin ellas.
El empate está en el 50%; por debajo, usar una habilidad no paga el turno que
cuesta.

- De las 1047 habilidades del plantel, 887 quedaron con efecto y 160 sin él
  (esquivar un golpe entero, resistir estados, aturdir, debilitar al rival).
  Por efecto: ataque 408, crítico 204, mana 150, curar 66, defensa 59. Por
  objetivo: 641 a uno mismo, 241 a quien elija, 5 a otro.
- Con los valores actuales la medida da **65%**, y las cinco familias quedan
  entre el 53% (mana) y el 70% (defensa). Ninguna es una trampa ni es la única
  que vale.
- El camino hasta ahí, porque cada paso enseñó algo:
  - Traduciendo las magnitudes de FGO tal cual, 7.7% con mediana 0: la IA
    perdía por gastar turnos en bonos que no pagaban.
  - Haciendo que la IA mida en ataques y solo use lo que paga, 54.8%, pero
    porque casi no las usaba.
  - Con los valores nuevos y la IA usándolos, 18.1%: encadenaba habilidades y
    el bono de la anterior se iba sin cobrarse.
  - Prohibiéndole encadenarlas, 32.6%. Enseñándole a cargar el golpe antes del
    Noble Fantasma, 43.9%. Lo que faltaba no era daño: era el mana que se
    pierde al no atacar. Con 10 de mana por habilidad, 70.8%, y afinando los
    valores (defensa 50%→35%, crítico 50→45, mana 70→60, curar 15%→12%), 65%.
- El nivel pesa lo mismo que antes hasta el 5: 1 nivel de ventaja da el 76%, 2
  el 83% y 3 el 89%. Con 5, que es cuando entra la primera habilidad, sube al
  99% (antes 97%). La XP del día 1 contra los NPC sigue en 157, y del nivel 5
  en adelante sube a 162 porque los bonos multiplican más al que es más fuerte.
- Las habilidades ensanchan el plantel, y con estos valores bastante. Con los
  mismos parámetros (8 rivales al azar x 12 combates), el plantel de nivel 1,
  donde no hay habilidades, tiene una desviación del 7.6% y 16 personajes
  fuera de la banda 35-65%; el de nivel 15 sube a **18.6% y 165 fuera**, con
  un máximo del 92.7% y un mínimo del 6.2%. Con las magnitudes de FGO eran
  10.1% y 33. Está en `puntos-abiertos.md`, porque hay que decidir qué hacer.

## Idioma

Fecha: 2026-11-06.

- **El bot se juega en español o en inglés.** Nada más por ahora, pero añadir
  un idioma es añadir una línea por frase y nada de código.
- **El idioma por defecto es el inglés**, porque es el que entiende más gente.
  Es el que usan una guerra creada sin elegir idioma y sin que Discord diga
  otra cosa, los nombres de los comandos que ve quien tenga Discord en un
  idioma que no tenemos, y cualquier texto que se pida sin decir en cuál. El
  español es una traducción más, no el original: está en `IDIOMA_POR_DEFECTO`,
  en `textos.py`, y cambiarlo es cambiar esa línea.
- **Ninguna frase se escribe en el código.** Todas viven en
  `bot/data/textos.json`, igual que los personajes, y se piden por clave con
  `game.textos.t("clave", idioma, ...)`. Son 103 claves.
- **Se valida al cargar**, como el presupuesto de estadísticas: si a una clave
  le falta un idioma, o los huecos entre llaves no coinciden entre idiomas, el
  catálogo revienta al arrancar. Una traducción a medias se vería como texto
  crudo en Discord, y eso no se nota hasta que lo ve un jugador.
- **El idioma lo elige quien crea la guerra** (`/crear-guerra`), y vale para
  todo el canal, lo público y lo privado. Si no elige, se usa el que trae
  Discord del creador. La razón: una guerra se narra en público, y media
  conversación en cada idioma no se entiende. Que cada jugador vea lo privado
  en su propio idioma es posible —Discord manda el idioma en cada
  interacción— y queda como punto abierto.
- La `Batalla` lleva su idioma dentro, y es lo único que cambia: medido, el
  mismo combate con la misma semilla da el mismo resultado, los mismos turnos
  y la misma vida en los dos idiomas. El idioma escribe, no decide.
- **Las fichas escritas a mano pueden traer su inglés**: `nombre_en` en una
  habilidad y `descripcion_en` en un rasgo. Y renombrar una habilidad al
  español guarda automáticamente como inglés el nombre que trajo el
  importador, así que traducir no deja la guerra en inglés sin nombres.
- Los nombres de los personajes y de los Nobles Fantasmas no se traducen: son
  nombres propios y vienen de Atlas Academy en inglés.
- Nada de "1 persona(s)": las palabras que se cuentan tienen su singular y su
  plural de verdad (`textos.plural`), y una prueba comprueba que no se cuela
  ningún "(s)" en el catálogo.
- El español del catálogo va sin acentos, como el resto del texto del bot,
  porque el registro de batalla también se imprime en la consola de Windows
  desde el simulador.
- Los nombres de los comandos (`/crear-guerra`, `/estadisticas`) siguen en español en
  los dos idiomas: localizarlos necesita un `Translator` de discord.py y
  queda pendiente.

## Niveles

- Nivel máximo 15, alcanzable dentro de una guerra.
- Habilidades desbloqueadas a los niveles 5, 10 y 15.
- Curva de XP propuesta y aceptada: del nivel n al n+1 hacen falta 20 + 5×n de XP.
- Cómo suben de nivel los personajes y sus estadísticas se discutirá después.

## Clases y personajes

- 8 clases: Saber, Archer, Lancer, Rider, Caster, Assassin, Berserker y Ruler.
- La clase solo decide el cupo en la invocación y el triángulo. Las estadísticas, el rasgo, las habilidades y el Noble Fantasma son del personaje.
- 7 cupos por guerra, uno por clase base. El Ruler aparece con un 5% y ocupa el cupo de una clase base, que no participa en esa guerra.
- Triángulo: Saber vence a Lancer, Lancer a Archer, Archer a Saber. Ventaja +10%, desventaja −10%. Las demás clases neutrales.
- Presupuesto de estadísticas: los tres multiplicadores de cada personaje suman 3.00 y ninguno sale del rango 0.55 a 1.35. Se valida al cargar.
- Las fichas de personaje viven en `bot/data/personajes.json`, fuera del código.

## Azar del combate

- El daño varía ±30% y hay 15% de crítico a ×1.8.
- La velocidad decide el orden de acción y además da esquiva sin defenderse: el 60% de la ventaja relativa de velocidad, con tope del 30%. Calibrado contra el plantel completo de 349: al 50% la velocidad no valía nada, al 80% las clases lentas se hundían (Berserker 41% contra Saber 54%), al 60% las 8 clases quedan entre 47% y 52%.
- Berserker: su rasgo es la demencia, ataca a un objetivo al azar en vez de al que elige su Maestro. Se probó quitarle la defensa y resultó ser un beneficio, no un castigo.
- Crecimiento por nivel: 3% de vida y ataque, 2% de velocidad, en proporción a la ficha.
- Factores de dificultad de los NPC: 0.55, 0.68, 0.80 y 0.92, endureciéndose un 3% por día.

## Hallazgos del simulador

- El presupuesto de 3.00 solo es justo si las tres estadísticas valen lo mismo. Hubo que calibrar la esquiva por velocidad para lograrlo.
- Desequilibrarse entre vida y ataque también pierde: se multiplican entre sí, así que lo equilibrado rinde más. Los especialistas pagan un pequeño impuesto.
- Velocidad por rareza: descartado. Las estrellas no se usan para balancear.

## Cómo se derivan las estadísticas desde los datos de FGO

Los datos de FGO no sirven como base directa: no tienen velocidad, están ordenados por rareza en vez de por equilibrio y están afinados para un juego distinto. Se usan para el plantel (nombres, clases), los nombres de habilidades y Nobles Fantasmas, los rasgos, y la proporción entre vida y ataque de cada personaje.

- La velocidad sale solo de la clase: Assassin 1.15, Rider 1.10, Lancer 1.05, Saber y Archer 1.00, Ruler 0.95, Caster 0.90, Berserker 0.85.
- Vida + ataque = 3.00 − velocidad, repartido según la proporción HP:ATK que el personaje tenga en los datos.
- Si la proporción es tan extrema que un multiplicador saldría del rango 0.55 a 1.35, se recorta y el sobrante va al otro.
- Consecuencia conocida: todos los personajes de una misma clase comparten velocidad. Pendiente de decidir si se añade un ajuste manual de −0.10 a +0.10 por personaje.

## Plantel importado

- Fuente: Atlas Academy, `export/NA/basic_servant.json`. 427 Servants, de los cuales 349 son de nuestras 8 clases.
- El export ligero ya trae `hpMax` y `atkMax`, así que basta para las estadísticas. El grande (`nice_servant.json`, 45 MB) añade los nombres de las habilidades y de los Nobles Fantasmas, y es el que usa el importador cuando está presente.
- Importado con el grande: 350 personajes, los 350 con Noble Fantasma y 349 con las tres habilidades (Solomon no tiene ninguna en los datos).
- Las habilidades vienen con `num` 1, 2 y 3, y un personaje puede traer varias versiones del mismo número porque el juego las mejora con el tiempo: se toma la primera de cada número. Igual con el Noble Fantasma.
- La clave de emparejamiento es `collectionNo`, no el nombre: hay 11 nombres repetidos (dos Cú Chulainn, tres Medusa) que se desambiguan añadiendo la clase.
- `EXAGERACION` en el importador controla cuánto se separan los extremos del plantel. Está en 1.5.
- Resultado medido: mediana del 50% de victorias, desviación del 7%, y 16 de 349 personajes fuera de la banda 35-65%.

## Los archivos se recuperaron de la transcripcion de la sesion

El 2026-11-07 siete archivos volvieron solos a su version del 2026-11-05:
`src/game/personajes.py`, `src/game/servant.py`, `src/commands.py`,
`tests/test_personajes.py`, `tools/importar_servants.py`, `docs/decisiones.md`
y `.gitignore`. No hay repositorio git, no hay copia de seguridad y OneDrive no
cubre la carpeta, asi que la unica fuente era la transcripcion de la sesion
(`~/.claude/projects/.../<sesion>.jsonl`), que guarda cada `Write`, `Edit` y
`Read`.

Lo que se aprendio reconstruyendolos, por si vuelve a pasar:

- **Una lectura completa de un `Read` es una foto fiel del archivo**, y vale
  mucho mas que reaplicar doscientos Edits a ciegas. El metodo que funciono fue
  partir del archivo tal como estaba, aplicar las escrituras en orden y **en
  cada foto comparar y adoptar la foto**; lo unico sin red es la cola posterior
  a la ultima foto, y eso lo cubren las pruebas.
- **La transcripcion guarda cada `tool_use` dos veces.** Sin descartar los
  repetidos por su id, cada Edit se aplica dos veces y los que insertan un
  bloque lo duplican: `commands.py` salio con 3146 lineas en vez de 1960.
- **Lo que cambio un script no esta en la transcripcion.** El renombrado
  Maestro/Sirviente a Master/Servant y el de `_narrar_cierre` a `narrar_cierre`
  se hicieron con scripts, no con Edits, asi que hubo que repetirlos a mano
  sobre lo reconstruido.
- **`.gitignore` no se pudo recuperar** porque no tiene ni una escritura ni una
  lectura en la transcripcion. Resulto no hacer falta: la version a la que
  volvio ya nombra `.env`, los volcados crudos de Atlas Academy y
  `bot/data/imagenes/`, y no contiene nada del estado viejo.
- **`bot/data/personajes_generados.json` tambien habia vuelto atras** (las
  habilidades como texto suelto, sin rango ni efecto) y no estaba en la lista.
  Ese no se recupera: se regenera con `python tools/importar_servants.py`, que
  es justo para lo que esta. Seis pruebas lo delataron.
- La comprobacion fue por marcadores (lo que tiene que estar porque es trabajo
  reciente y lo que no puede estar porque es del estado viejo) mas `ast.parse`,
  y al final las 330 pruebas y `tools/comprobar_bot.py`.

**Mientras no haya un repositorio git, un archivo perdido se recupera de la
transcripcion o no se recupera.** Conviene `git init` antes de la siguiente
tanda de trabajo.

### El respaldo que sale de esto

A partir del 2026-11-07, antes de modificar un archivo se guarda como estaba en
`.respaldo/<AAAA-MM-DD>/`: una subcarpeta por dia, la copia antes del primer
cambio del archivo en la sesion, y no se sobrescribe despues, porque la primera
copia es la que vale. La carpeta esta en `.gitignore`, y la regla esta tambien
en `CLAUDE.md` para que no dependa de que alguien se acuerde.

No sustituye a git: guarda una sola version por dia y solo de lo que se toco.
Lo que de verdad cierra el agujero es `git init`, que sigue pendiente.

## Terminar una guerra a mano: se cancela, no la gana nadie

`/terminar-guerra` (`/end-war`) cierra la guerra del canal. Lo pensamos para la
guerra que se atasca, la que se abandona a medias y la que se abre por error, y
de esas tres cosas sale la decision de fondo: **cancelar no es ganar**. No hay
ganador, no se entrega el Grial, y da igual cuanta gente quedara en pie.

Se descarto la otra opcion, que era acabar la guerra declarando ganador al que
menos derrotas lleva. Suena comodo para una guerra que se alarga, pero el
comando es del creador, y el creador sabe como va: cerrar la guerra justo
cuando vas ganando es ganar escribiendo un comando. Si alguna vez hace falta
acabar antes una guerra larga, el camino no es un botonazo del creador, es un
limite de dias que valga para todos.

Detalles que no son adorno:

- **`Guerra.cancelada` existe aparte de la fase.** `ganador()` cuenta los
  activos, asi que si solo se mirara `Fase.TERMINADA`, cortar una guerra en la
  que ya solo quedaba uno vivo lo coronaria. Con el `cancelada`, `ganador()` y
  `gana_el_grial()` devuelven `None` siempre.
- **No se guarda en la base de datos, y no hace falta.** Cancelar deja la fase
  en TERMINADA, y eso es lo que hace que `repositorio.guardar` ponga
  `terminada_en`; una guerra con `terminada_en` no la vuelve a cargar
  `cargar_todas`. La fila se queda: una guerra terminada se marca, no se borra.
- **Cancelar tiene que limpiar lo que vive fuera de la `Guerra`.** La batalla
  en curso esta en `self.combates` del Cog, asi que `terminar_guerra()` la
  borra; si se quedara ahi, el vigilante seguiria intentando avanzar la batalla
  de una guerra que ya no se juega. Y pone `vence_preparacion` a 0, para que no
  le cierre dias.
- **Entre el comando y el final hay un boton rojo.** Terminar no se deshace y
  un comando suelto se escribe sin querer, asi que el comando solo pregunta, en
  privado, y lo que cierra la guerra es `ConfirmarTerminar`. Caducar es no
  hacer nada.
- **El final se cuenta en el canal, el susto no.** La pregunta es privada (si
  el creador se arrepiente, nadie tiene por que haberlo visto), pero el cierre
  es publico: la guerra es de los siete. El aviso dice el dia y cuantos
  quedaban en pie, y **no nombra ningun Servant**, porque la regla del secreto
  no se levanta porque la guerra se acabe.
- Despues de cancelarla el canal queda libre y `/crear-guerra` abre otra ahi
  mismo, igual que con una guerra acabada jugando.

## El arte oficial: copia local si, publicarlo no

Decidido el 2026-11-09, y es un cambio de la primera decision del proyecto, que
decia "sin arte oficial" a secas. La regla nueva parte en dos lo que antes era
una sola cosa:

- **Tener una copia local, si.** `tools/descargar_imagenes.py` baja el
  `charaGraph` de Atlas Academy a `data/imagenes/`, que esta en `.gitignore`.
  Sirve para desarrollar y para mirar el plantel. Cada uno baja la suya: el
  repositorio lleva el script, no las imagenes.
- **Que el bot las publique, no.** Nada en `src/` lee `data/imagenes/` y nada
  envia archivos a Discord. Lo que el jugador ve es texto: nombre, clase, rango.

El porque de la linea donde esta: una copia en tu maquina es como tener el juego
instalado, y subirla a Discord es volver a publicar la obra para gente que no la
tiene. La primera es un riesgo bajo en un proyecto de fans entre amigos; la
segunda es distribuir arte de otros, y no se hace de rebote por conveniencia.
Los datos no estan en el mismo caso y por eso si se usan: las estadisticas y los
nombres son informacion **sobre** la obra, el arte **es** la obra.

**La regla esta puesta en una prueba, no solo escrita.** `tests/test_arte.py`
falla si algun modulo de `src/` nombra el directorio de imagenes o manda un
archivo a Discord. No es que enviar un archivo sea malo para siempre: es que
cruzar esa linea tiene que ser una decision y no un descuido, y la prueba
obliga a venir aqui a cambiarlo. La misma prueba comprueba que el plantel sigue
trayendo las URLs, que es lo que se perdio el 2026-11-07 y dejo
`descargar_imagenes.py` sin nada que bajar.

Medido antes de bajarlas: unos 556 KB por imagen, 349 en la ascension 1 (unos
189 MB) y 1396 contando las cuatro ascensiones (unos 0.74 GB). Bajada la
ascension 1, que es el arte base y lo que necesitaria una carta; las otras tres
se bajan cuando hagan falta, porque el script es reanudable.

### Las cuatro ascensiones se reparten por nivel

Idea de Cristopher el 2026-11-09: cada personaje tiene cuatro artes, asi que
usarlas segun el nivel en vez de quedarse con una. Las bandas son 1-4, 5-9,
10-14 y 15, y lo decide `Servant.ascension`, que devuelve "1", "2", "3" o "4"
(texto, porque es la clave del diccionario `imagenes` del plantel).

Lo bueno del reparto es que **no hace falta elegir los cortes**: los que pidio
son exactamente `NIVELES_HABILIDAD = (5, 10, 15)`. Asi que `ascension` se
calcula contando habilidades desbloqueadas (`1 + cuantas`) en lugar de repetir
los numeros. Dos consecuencias:

- El aspecto cambia **justo** cuando se desbloquea una habilidad. Subir de
  nivel se nota en la ficha y en el dibujo a la vez, y no hay un nivel donde
  pase una cosa y no la otra.
- Si alguna vez se mueven los niveles de habilidad, el arte se mueve con ellos.
  Hay una prueba que lo dice en voz alta, no vale como comentario.

Comprobado: las 349 fichas traen las cuatro ascensiones, 1396 URLs, y para cada
nivel de 1 a 15 la ascension que pide existe como URL en el plantel. No puede
pedir una quinta, porque el nivel maximo es 15.

Sigue valiendo la regla de arriba: esto es **solo el numero**. Nada en `src/`
abre la imagen ni la manda a Discord.

### El bot enlaza el arte, no lo sube

Cambio del 2026-11-09, el mismo dia que la regla de arriba, y la prueba
`test_arte.py` es la que obligo a venir aqui antes de tocar el codigo: para eso
estaba.

Cristopher pidio que la ficha de un Servant ensene el arte, y que se pueda ver
el de los rivales con los que ya peleaste. La regla decia "el bot no publica
arte oficial". Lo que cambia no es si se ve: es **de donde sale el archivo**.

- **Lo que se hace:** un `discord.Embed` con `set_image(url=...)` apuntando a
  la URL de Atlas Academy. El bot manda un enlace; la imagen la pide el cliente
  de quien mira, al mismo sitio al que iria un navegador. El bot no guarda, no
  copia y no reparte nada.
- **Lo que sigue prohibido:** subir el archivo (`discord.File`,
  `discord.Attachment`). Eso pondria una copia del arte en el CDN de Discord,
  servida por nosotros a quien no la tenia. Esa es la linea, y no se mueve.
- **Y sigue siendo privado.** La ficha y el arte van en mensaje efimero, solo
  para quien lo pide. Ni el arte propio ni el de un rival aparecen en el canal:
  ensenar un Servant en publico delataria quien lleva que, que es la otra regla
  (ver *Nadie sabe que Servant lleva nadie hasta que pelea con el*).

La copia local de `data/imagenes/` sigue teniendo sentido aparte: sirve para
mirar el plantel y para armar cosas sin depender de la red. Lo que no hace es
alimentar al bot.

**El orden de la ficha** lo pidio asi y en Discord sale gratis, porque es el
orden de un mensaje: contenido, embeds y componentes. O sea texto (nombre,
clase y estadisticas), arte debajo y el menu al final. La ficha lleva el menu a
proposito: desde ella se sigue jugando en vez de quedarse en una pantalla sin
salida, y el boton del menu y el comando `/estadisticas` dejan la misma
pantalla.

**Ver el Servant de un rival no ensena su nivel ni sus estadisticas.** Solo
quien lo lleva, que Servant es, de que clase y el dibujo: exactamente lo que
`/estado-guerra` ya decia de un rival conocido. Contar su nivel seria
informacion nueva, o sea un cambio de balance, y eso se mide antes de hacerlo
(esta en puntos-abiertos.md). El boton se apaga mientras no hayas visto a
nadie, que es lo que te dice de un vistazo que todavia atacas a ciegas.

Detalle: `Servant.imagen` cae a la ultima ascension que el personaje si tenga
en lugar de quedarse en blanco. Un personaje al que le falte la cuarta se ve
con la tercera al llegar al nivel 15, que es mejor que no verse.

## El plantel son 348: fuera el que no se puede invocar

Decidido el 2026-11-09. Lo encontro la descarga del arte: al collectionNo 0,
"Henry Jekyll & Hyde (Berserker)", le fallaban las cuatro URLs con 404. La
pregunta era si ponerle un parche, y al mirarlo result que el parche no hacia
falta porque el personaje no tenia que estar.

**Ese numero 0 es Hyde**, la forma Berserker en la que se transforma Jekyll, que
ya esta en el plantel por su cuenta con el numero 81 (Assassin). No se invoca:
es una transformacion dentro del combate del juego original. Tenerlo era tener a
Jekyll dos veces, uno de ellos sin arte.

**La regla se escribio por el cupo, no por el nombre.** Un Servant que no se
puede invocar no ocupa sitio en la coleccion, y por eso su `collectionNo` es 0.
El importador descarta a los que valen 0 (`SIN_CUPO_EN_LA_COLECCION`), asi que
si el export trae otra forma parecida se cae sola, sin tocar nada. Quitar "a
Hyde" por su nombre habria sido un caso especial que no protege de nada.

Hay una prueba en `tests/test_arte.py` que falla si vuelve a entrar alguien con
el numero 0.

### Medido, porque es un cambio de balance

Quitar uno **mueve a los 348 restantes**: la mediana HP:ATK del plantel entra en
el reparto vida/ataque de cada personaje, asi que cambiar quien esta en el
plantel cambia los numeros de todos. Habia que medirlo antes de darlo por bueno.

- **Las 348 fichas cambiaron, y el que mas se movio lo hizo 0.002** (vida
  -0.002, ataque +0.002). Es un movimiento de redondeo.
- Ninguna ficha se salio del presupuesto de 3.00 ni de la banda 0.55-1.35.
- El simulador (`plantel`, semilla 7) paso de desviacion 6.3% y 6 fuera de la
  banda 35-65%, a 5.3% y 4. **Eso es ruido, no una mejora**: con otras semillas
  sale 6.2% y 5, 5.7% y 5, y 5.6% y 7, asi que el "antes" cae dentro de la
  dispersion. La conclusion honesta es que el balance no cambio.

Efecto secundario que si se nota: la descarga del arte ya esta completa. **1392
imagenes de 1392** (737 MB), sin ningun hueco, porque las 4 que faltaban eran
precisamente las suyas.

Los numeros de 349 que quedan en este documento y en `puntos-abiertos.md` son
medidas de cuando el plantel eran 349 y **se dejan como estaban**: dicen contra
que se midio, y reescribirlos seria falsear el registro.

### Donde se ensena el arte, y donde no

Al 2026-11-09 hay tres sitios, y los tres son mensajes efimeros:

1. **La invocacion.** Al pedir tu Servant, el mensaje privado trae su nombre, su
   clase, tus sellos y el arte. Es el primer momento en que lo ves, asi que es
   donde el dibujo hace mas.
2. **La ficha** (`/estadisticas` y el boton del menu): texto, arte y menu.
3. **Los Servants que conoces**, los de los rivales con los que ya peleaste.

Y un sitio donde **no** se ensena, que es la regla de verdad: **el canal**. La
invocacion anuncia que invocaste y cuantos faltan, nunca a quien; ensenar el
dibujo en publico le regalaria tu Servant a los otros seis, y entonces declarar
un ataque dejaria de ser una apuesta a ciegas (ver *Nadie sabe que Servant lleva
nadie hasta que pelea con el*). Hay pruebas que recorren los mensajes publicos
de la invocacion y exigen que no lleven ni el nombre ni embed.

`arte_del_servant()` devuelve `None` sin Servant y sin URL, asi que ningun sitio
tiene que preguntar las dos cosas antes de llamarla. Lo de "sin Servant" pasa de
verdad: la invocacion puede fallar, y entonces no hay nada que ensenar.


## El inventario de los Masters: objetos con una lista cerrada de efectos

**Decidido el 2026-11-09.** Un Master lleva objetos encima y los usa dentro y
fuera del combate. La forma es la misma que la de las habilidades, a propósito:
**del dato sale qué efecto tiene un objeto; cuánto da lo decide el juego**
(`VALOR_POR_EFECTO_DE_OBJETO` y `VALOR_POR_EFECTO_FUERA`, en
`game/objetos.py`). Así un objeto nuevo en `data/objetos.json` no puede traer
un número roto: no trae números.

Las piezas:

- **`game/objetos.py`**, el dominio. `Momento` dice cuándo se usa (combate,
  preparación, invocación), y según el momento el objeto lleva uno de los
  cinco `Efecto` del combate que ya existían, uno de los tres `EfectoFuera`
  nuevos (XP, curar antes de pelear, un combate NPC más) o una `Clase`, si es
  un catalizador. Un objeto hace **una sola cosa** y se valida al cargar,
  igual que un personaje: si no cuadra, no entra.
- **`data/objetos.json`**, 16 objetos. Este sí se edita a mano, al contrario
  que `personajes_generados.json`.
- **`Inventario`**, dentro del `Master`. Es un contador por clave, un tope de
  25 y un contador de usos de la batalla en curso.

**No hizo falta ninguna regla nueva en el combate.** Los objetos de combate
mueven las cinco perillas que `battle.py` ya tenía, así que `_aplicar_efecto`
sirve igual para una `Habilidad` y para un `Objeto`: solo lee `efecto`,
`valor` y `turnos`. Esa es la razón de que los efectos sean los mismos y no
una lista aparte.

### Usar un objeto no cuesta el turno, y por eso da menos

Una habilidad gasta el turno entero: un ataque **y** sus 15 de maná (ver *Las
habilidades cuestan el turno*). Un objeto no gasta nada. Con los mismos
números, un objeto sería una habilidad gratis, o sea estrictamente mejor que
cualquier habilidad, y las habilidades dejarían de valer. Así que los objetos
tienen sus propios valores, a dos tercios de los de la habilidad del mismo
efecto (`FRACCION_DE_LA_HABILIDAD`), y hay una prueba que lo exige objeto a
objeto. La excepción a mano es curar, que no tiene habilidad equivalente que
pague el turno.

Lo segundo que lo sostiene es el tope: **un objeto por batalla**
(`OBJETOS_POR_BATALLA`). Sin tope, una batalla la decidiría quien llevara más
objetos encima y no quien peleara mejor.

El tope vive en el `Inventario` del Master, **no en `Combate`**: el objeto y su
tope son suyos, y una batalla no sabe de inventarios. `Combate.usar_objeto`
comprueba lo de la batalla (que no haya acabado, que estés dentro, que no
hayas caído) y nada más; lo del tope lo comprueba el Cog antes de llamar.

`usar_objeto` **no toca `self._decisiones`**: después de usar el objeto sigues
teniendo que elegir tu acción, y el turno se cierra cuando deciden todos,
igual que siempre.

### De dónde salen: el entrenamiento, con la probabilidad que ya había

Los suelta el NPC al que ganas, con `PROB_OBJETO` (de 0.10 el primero a 0.40
el cuarto), que ya existía con un objeto de mentira. Qué sale lo sortea
`objetos.sortear`, pesado por lo común que es cada objeto. **Los catalizadores
tienen peso 0 y no se sueltan**: apuntan la invocación, que es del día 1, así
que llegarían tarde.

Con el inventario lleno, la suelta **se cuenta y se pierde**. Guardarlo en una
cola invisible sería un sistema entero por un caso que solo pasa con 25
objetos encima, y reventar le rompe el día a quien acaba de ganar.

### Los objetos duran la guerra; lo que vuelve a cero es el uso por batalla

`Master.nuevo_dia()` llama a `inventario.nueva_batalla()`, que solo pone a cero
`usados_en_la_batalla`. Y el inventario **se guarda en la base de datos**
(columna `inventario` de `masters`, un JSON de clave a cuántos), porque una
guerra dura días y reinicios. El contador de la batalla no se guarda: es de la
batalla en curso, que vive en memoria. Un inventario ilegible se registra y
vuelve vacío, al contrario que un Servant que falta, que tumba la guerra
entera: sin Servant no hay con qué pelear, sin objetos sí.

### El secreto se mantiene

El texto de usar un objeto **nombra el objeto**, así que
`usar_objeto_en_combate` lo **devuelve** en vez de mandarlo a ningún sitio, y
quien lo llama lo manda efímero. El detalle va al `ultimo_registro` del
Master, como el resto de la batalla. Al canal no llega nada: decir que ese
Master usó una gema delataría lo que lleva encima.

### Lo que se midió

Cuatro semillas de 600 guerras, una persona contra 6 bots: 14.2%, 15.0%,
14.5% y 11.2% (le toca el 14.3%). Es la misma banda de ruido de siempre, o sea
**que el inventario no movió la justicia de la guerra**, y tiene que ser así
porque los bots no usan objetos. Lo que esto **no** mide es el balance de los
objetos en sí: ni la IA ni el simulador los usan todavía, así que
`VALOR_POR_EFECTO_DE_OBJETO` es por ahora un número razonado y no un número
medido. Está apuntado en `puntos-abiertos.md` y es lo primero que hay que
cerrar del inventario.

### El catalizador está sin cerrar a propósito

La categoría, el dato y el inventario existen; la mecánica no. Usar uno
contesta `inventario.catalizador_pendiente` y **no lo gasta**. Lo que no podía
pasar es que se perdiera un objeto por una mecánica que todavía no está.


## La tienda y las dos monedas: oro y griales

**Decidido el 2026-11-09.** Hay una tienda, y tiene dos monedas que no son dos
formas de lo mismo: **miden cosas distintas y por eso duran distinto**.

| | de dónde sale | cuánto dura | qué compra |
|---|---|---|---|
| **Oro** | ganar un NPC de entrenamiento y ganar una batalla | **muere con la guerra** | objetos de combate y de preparación |
| **Griales** | ganar una guerra | **se quedan en la cuenta** | catalizadores |

La razón de que el oro no se guarde entre guerras es que sería una cuenta de
ahorros: el que llevara diez guerras empezaría la once con todo comprado, y una
guerra nueva dejaría de empezar empatada. Lo único que vale la pena arrastrar de
una guerra a la siguiente es **el derecho a elegir con quién entras en la
próxima**, y eso es exactamente lo que compran los griales.

Por eso el oro vive en el `Master` (que muere con la guerra, y se guarda en su
columna `oro`) y los griales en una `tienda.Cuenta`, en la tabla `cuentas`, por
`usuario_id`. **`cuentas` es la única tabla que no cuelga de `guerras`**, y
existe solo por esto.

### El agujero obvio ya estaba cerrado: se paga por `gana_el_grial()`

Abrir una guerra solo contra 6 bots, ganarla y cobrar griales no se puede, y no
hubo que inventar ninguna regla: una guerra necesita 4 personas de verdad para
entregar el Grial (`MINIMO_HUMANOS_PARA_GRIAL`, que ya existía). Lo único que
había que hacer es **pagar por donde se entrega el Grial y no por donde queda
uno en pie**: `pagar_los_griales()` llama a `guerra.gana_el_grial()` y nunca a
`ganador()`.

Y se paga en `narrar_cierre`, que es el único sitio donde se anuncia el Grial y
por el que pasan los tres caminos que cierran un día. Es la misma lógica que
`anotar_batalla` con las derrotas: si se pagara en una puerta y no en otra,
habría guerras ganadas que no pagan.

### Los precios: 2 y 5 griales los puso Cristopher, el resto se midió

Un catalizador de clase cuesta **2 griales** y uno de un Servant concreto
**5**. Ganar una guerra da **2 griales** (`GRIALES_POR_GUERRA`), y de ahí sale
el ritmo: ganar una guerra es exactamente un catalizador de clase, y uno de
Servant son tres guerras. Lo justo para que la diferencia entre 2 y 5 se note.

Los precios en oro van de 40 a 70, y tienen dos anclas que no son cuestión de
gusto y por eso son pruebas:

- **El crítico es el más barato** (40, el ojo certero), porque es el efecto más
  flojo que tenemos.
- **El reloj de arena cuesta 70, más que los 30 del NPC más generoso.** Si
  costara menos, comprarlo y pelear daría oro, y una tienda que fabrica oro no
  es una tienda. Se compra por la XP y por lo que suelte, no por el oro.

Lo que paga el juego: **10/15/20/30 de oro** por cada NPC de la escalera (de
menos a más, como la XP y como la probabilidad de suelta: pelear arriba tiene
que pagar más) y **50 por salir en pie de una batalla que tumbó a alguien**. Un
empate no paga, porque lo que se cobra es ganar y no estar.

### Lo que se midió

`python -m src.simulator --semilla 7 economia -n 200`, un modo nuevo:

```
  dias por guerra:  3.9
  oro por Master:   216 de media
                    90 el decil bajo, 195 la mediana, 400 el decil alto
  objetos baratos:  5.4 con el oro medio (40 c/u)
  objetos caros:    3.1 con el oro medio (70 c/u)
  comprarlo todo:   450 (2.1 guerras)
```

Sale igual con 1 o con 7 personas en la mesa (206 y 220), porque el oro sale
casi todo de entrenar y entrenar no depende de cuánta gente haya. Con 216 se
compran **de 3 a 5 objetos**, y en una guerra de 4 días solo se pueden **usar**
4 de combate (uno por batalla). O sea: da justo para ir armado a tus batallas y
poco más, que es lo que se buscaba. Comprarlo todo cuesta 450, dos guerras:
inalcanzable a propósito.

La justicia de la guerra **no se movió ni un dígito**: 14.2% / 27.5% / 58.0% /
100.0%, idénticos a los de antes de la tienda. Tenía que salir así, porque la
economía no toca el combate ni consume números del azar, y que salga idéntico
es la comprobación de que no los toca.

### El escaparate se ve aunque no se pueda comprar

La tienda **solo abre en la preparación**, y eso es una regla de juego y no una
comodidad: si se pudiera comprar dentro de la batalla, el objeto dejaría de ser
algo que decides llevar y sería algo que saca de la nada el que vaya perdiendo.
Tampoco se compra después de decirse listo, por lo mismo que no se entrena ni
se cambia de objetivo.

Pero el **texto** de la tienda se enseña igual, con los precios, aunque no se
pueda comprar nada: saber a cuánto está un elixir es parte de decidir si
entrenas otra vez. Igual que el inventario, que también se ve entero.

### Comprobar, cobrar, entregar: en ese orden

Las dos funciones de compra (`comprar_con_oro`, `comprar_catalizador`)
comprueban **todo** antes de tocar nada, y solo entonces cobran y entregan. Es
el mismo orden que `usar_objeto_en_preparacion`, por la misma razón: cobrar sin
entregar es el único error de una tienda que de verdad enfada. Con el
inventario lleno no se cobra, y hay una prueba para cada moneda — perder 5
griales así serían tres guerras ganadas tiradas.

### Los catalizadores de Servant no están en el catálogo

Los de clase son 8 y están en `objetos.json` como cualquier otro objeto. Los de
Servant serían 348, así que **se arman al pedirlos**
(`objetos.catalizador_de_servant`) y su clave lleva el número dentro:
`catalizador_servant:91`. `objetos.objeto()` reconoce esa forma, y por eso un
inventario guardado con uno dentro se lee igual que cualquier otro: si no lo
reconociera, un catalizador de 5 griales desaparecería al recargar la guerra.

La clave lleva el `collectionNo` y no el nombre por lo de siempre: los nombres
no son únicos y se traducen.

**Se elige escribiendo el nombre**, en un `discord.ui.Modal`, porque son 348 y
un desplegable de Discord aguanta 25. Si lo que escribió encaja con varios no
se compra ninguno y se le enseñan los que encajan: no hay ningún Servant que se
llame "Medusa" a secas (los repetidos se desambiguan con la clase), así que
escribir "Medusa" tiene que contestar "hay tres" y no cobrar. El nombre exacto
gana al parecido, para que "Altria Pendragon" no se quede en ambiguo para
siempre por culpa de "Altria Pendragon (Alter)".

### Lo que sigue sin decidirse

**Qué hace un catalizador al usarlo.** Se compran, se guardan y se ven, pero
usar uno sigue contestando que la mecánica está sin cerrar, y **no se gasta**.
Comprar ya tiene sentido (es un ahorro con un destino), pero el efecto en la
invocación es la pieza que falta y Cristopher la va a explicar. Está en
`puntos-abiertos.md` con las preguntas concretas que hay que contestar.


## Repartir el turno entre los que pelean

**Arreglado el 2026-11-09**, y el fallo lo encontró jugando Cristopher con un
amigo: en una batalla de dos personas, **el turno solo se lo veía una**.

La causa está en la forma de `Combate.decidir`: las decisiones de un turno son
simultáneas, así que mientras falta gente devuelve `[]` y el turno se resuelve
con la decisión del **último**. Los eventos se los lleva, entonces, quien
decidió último. Al otro le quedaba "tu decisión queda apuntada" y nada más. Y
lo peor no era no ver el turno, era **no tener forma de saber que había pasado
algo**: el menú tenía un botón de *Refrescar*, pero nadie refresca lo que no
sabe que ha cambiado.

Estaba apuntado en `puntos-abiertos.md` como una incomodidad ("los demás pulsan
Refrescar") y no lo era: con dos personas de verdad, la batalla parecía
colgada.

### Lo que sí se puede hacer con un mensaje efímero

Discord no deja mandarle un mensaje efímero a nadie de la nada, y de ahí venía
la decisión vieja. Pero sí deja **contestar otra vez a una interacción que ya
existe**, durante 15 minutos: `edit_original_response()` para reescribir el
mensaje que ya le mandaste y `followup.send()` para mandarle otro.

Así que el Cog se queda con por dónde hablarle a cada uno:

```
self.mesas: (guerra.id, master.id) -> (su ultima interaccion, su menu)
```

Se apunta en dos sitios y los dos hacen falta: al abrir el combate desde el
botón del canal (el caso del fallo: abres tu combate y te quedas mirando) y en
`MenuCombate.interaction_check`, por donde pasan **todos** los botones del
menú, así que la interacción que se guarda es siempre la más reciente. Eso
importa porque la vieja caduca a los 15 minutos.

Vive en memoria y muere con las batallas, en el mismo sitio donde muere
`self.combates`: el menú que tenían delante es de un día que ya pasó.

### A cada uno se le hacen dos cosas

`repartir_el_turno` le **reescribe el menú** (su vida, su maná y lo que puede
hacer han cambiado) y le **manda el turno en un mensaje nuevo**. Las dos: el
menú reescrito deja la mesa al día, pero lo que de verdad avisa es el mensaje
nuevo, porque un mensaje editado no notifica a nadie.

Por eso `MenuCombate.refrescar()` perdió el guion bajo: ya no es privado,
porque el Cog tiene que poder refrescarle el menú a alguien que no ha tocado
nada.

**Solo a los de tu batalla**, no a toda la guerra: se saca de
`combate.humanos`, que es quién pelea en esa mesa. Contarle el turno a quien
pelea en otra sería contarle una batalla en la que no está, y eso es
exactamente lo que la regla del secreto no permite. A los bots tampoco, que no
tienen Discord al que hablarles, y `humanos` ya los deja fuera.

**Que no se pueda avisar no es un error.** La interacción caduca a los 15
minutos y el mensaje efímero se puede haber cerrado: se registra en el log y se
sigue. El turno ya pasó, y la batalla no puede quedarse parada porque alguien
cerrara una ventana. Para ese caso el botón de *Refrescar* sigue ahí, y por eso
no se ha quitado.

### Dos cosas que hay que hacer después de cada decisión, en un solo sitio

Repartir el turno y cerrar el día (si esa fue la última decisión) se olvidan
las dos solas, así que viven juntas en `despues_de_decidir`, que es a lo que
llama ahora cada camino del menú de combate. Antes cada camino llamaba a
`cerrar_si_acabaron_los_combates` por su cuenta, y eran cinco sitios donde
olvidarse del segundo.

### La prueba se comprobó al revés

`PruebaRepartirElTurno` monta una guerra con dos personas en la **misma**
batalla (no basta con que las dos declaren: `formar_batallas` puede
separarlas, y el segundo tiene que decirse listo o el día no se cierra) y
ataca con los botones de verdad, no llamando al método del Cog. Con el arreglo
desactivado a mano, `test_el_camino_de_verdad_avisa_al_otro` falla con
exactamente lo que vio Cristopher: al primero no se le avisó de nada. Esa es
la única forma de saber que una prueba de un fallo sirve para algo.


## La cuarta puerta: el dia se cierra cuando ya no falta nadie

**Hecho el 2026-11-09**, y lo pidio Cristopher: *"necesito que si todas las
personas acaban su dia que se inicie automatico los combates"*.

Antes decirse **Listo** solo apuntaba que ya estabas, y el dia lo tenia que
cerrar el creador con el boton rojo. Eso era pedir un clic que no decidia nada:
el boton rojo ya exigia que **todos** estuvieran listos
(`aviso_si_no_se_puede_cerrar`), asi que cuando se podia pulsar no quedaba nada
que esperar. Si el creador no estaba mirando, la guerra se quedaba parada hasta
que venciera el plazo, con todo el mundo listo.

Ahora decirse listo el ultimo cierra el dia y abre los combates.

### Cuatro puertas, una sola puerta

Ya eran tres (`/empezar-batallas`, el boton rojo del menu y el vigilante de
plazos) y la regla de la casa era que **las tres tienen que dejar la misma
mesa**: los textos del cierre *y* el boton que toque en el canal (abrir tu
combate si hay batallas, el del menu si empieza un dia nuevo, o ninguno si la
guerra acabo). Con cuatro, repetir eso cuatro veces era garantizar que una se
quedara atras.

Asi que las cuatro llaman a lo mismo:

```
cog.cerrar_el_dia(guerra, enviar, por_plazo=False)
```

Lo unico que cambia entre ellas es **por donde se habla**, y eso se pasa como
argumento: `enviar_por(interaction)` para las tres que nacen de un clic (y que
sabe si a esa interaccion ya se le contesto, con `response.is_done()`, porque
un comando todavia no ha respondido y un boton si) y
`enviar_por_el_canal(canal)` para el vigilante, que no tiene interaccion
ninguna. El `por_plazo` tambien es suyo: cambia la primera linea, que conviene
que se vea si el dia lo cerro la gente o el reloj.

`CogDeMentira`, en `tests/test_vigilante.py`, **toma prestados** `cerrar_el_dia`
y `enviar_por_el_canal` del Cog de verdad en vez de copiarlos. Si los copiara,
esas pruebas pasarian con una version propia y el vigilante de verdad podria
dejar otra mesa, que es justo el fallo que la puerta compartida existe para
evitar.

### La pregunta la hace un solo sitio

`puede_cerrarse_ya()` es lo que mira la puerta nueva, y pregunta **exactamente
lo mismo** que el boton rojo (`aviso_si_no_se_puede_cerrar`), no una version
parecida: si el boton y el cierre automatico mirasen cosas distintas habria
dias que no cierra ninguno de los dos. A un eliminado no se le espera (si se le
esperara, el dia no cerraria nunca) y quien no invoco tampoco bloquea, porque
`formar_batallas` invoca por quien falte.

Y el boton rojo **no se quita**: hace falta si alguien se dijo listo antes de un
reinicio. Lo que se hace es sacarlo del menu en el mismo clic que cierra el
dia, porque ofrecer cerrar lo que ya esta cerrado solo despista.

### Un menu de ayer no cierra el dia de hoy

Lo encontro una prueba, no una partida, y es la parte que no era obvia. Un menu
efimero se queda abierto en la pantalla de quien lo abrio. Si otro cierra el
dia mientras tanto, lo que tiene delante es de **ayer**, y decirse listo ahi le
cerraba el dia nuevo **sin haberlo jugado**: sin entrenar y sin declarar a
nadie. Antes no importaba, porque decirse listo no cerraba nada.

Asi que `MenuAccion` nace sabiendo de que dia es (`dia_del_menu`) y
`boton_listo` lo comprueba antes de nada: si la guerra ya va por otro dia,
contesta `menu.dia_viejo` en privado y no toca nada.

### Dos salidas, las dos correctas

Cerrar la preparacion no siempre deja `Fase.BATALLA`. Si al humano le toco
descansar, las batallas son todas de bots, salen ya resueltas y el dia se
cierra entero de corrido: la fase vuelve a ser `PREPARACION`, pero del dia
siguiente. Las dos son correctas, y a quien le toca pelear depende del orden en
que se recorren los Masters, que **cambia de una corrida a otra** porque Python
aleatoriza el hash de las cadenas. Tres pruebas que exigian `Fase.BATALLA`
fallaban una de cada tres veces sin que nada estuviera roto; ahora exigen "el
dia 1 se acabo" (`_acabo_el_dia_1`). Y `_montar` le pone semilla a la `rng` de
la guerra, que `/crear-guerra` deja sin poner a proposito: en una partida de
verdad tiene que ser aleatoria.

Son 13 pruebas (`PruebaElDiaSeCierraSolo`), y dos de ellas cierran dos guerras
iguales con la misma semilla, una por cada puerta, y comparan la mesa que
queda: el dia, la fase, si hay batallas en curso y que boton se quedo en el
canal. La regla de la casa, hecha prueba.


## Las habilidades que no hacían nada

**Medido y arreglado a medias el 2026-11-09**, y lo pidió Cristopher: *"quiero
revisar habilidades que están sin efecto"*.

El importador traduce los `funcType` y `buff` de FGO a nuestros cinco efectos y
**descarta el resto**, y lo que se descarta entra como `Efecto.NINGUNO`: una
habilidad con nombre, que se puede pulsar, y que no hace nada. Eran **159 de
1044 (el 15.2%), repartidas en 131 personajes**, y dos las tenían las tres:
Gilles de Rais (Caster) y Eric Bloodaxe.

### De qué estaban hechas

Clasificando cada función del export crudo, el reparto es muy desigual:

- **244 funciones se caen por el objetivo**, todas `enemy` (146) y `enemyAll`
  (98). Eso no es un fallo: los efectos negativos están fuera por diseño.
- **238 por el buff** y **71 por el `funcType`**. Los grupos grandes:
  `hastenNpturn` (53), `upDropnp` (47), `guts` (41+7), `invincible` /
  `avoidance` / `avoidState` (38), `upHate` (18).

### Lo que se tradujo, y por qué solo eso

Se tradujo lo que **ya era uno de nuestros cinco efectos con otro nombre**:
cargar antes el Noble Fantasma es maná (en FGO mueve el reloj de la carga; aquí
el reloj *es* el maná) y más vida máxima es curar. Seis entradas nuevas, y las
habilidades vacías bajaron de **159 a 117**. Eric Bloodaxe dejó de estar vacío
del todo.

No se tradujo lo que pide una regla nueva: esquivar, aguantar un golpe mortal,
provocar. Se pueden aproximar, pero eso ya no es traducir, y vale muy poco: 117
→ 115. Está en `puntos-abiertos.md`.

### Las traducciones nuevas van en segunda vuelta

Esto es lo que no era obvio. `habilidad_de` se queda con **la primera función
que sabe traducir**, así que meter las entradas nuevas en la tabla principal no
solo rellenaba huecos: le cambiaba el efecto a habilidades que ya tenían uno,
porque una función nueva podía aparecer antes en la lista de FGO. Se midió al
hacerlo: **5 habilidades de crítico y 1 de ataque se convertían en maná** sin
que nadie lo pidiera.

Por eso hay `EFECTOS_POR_BUFF_SECUNDARIOS` y `EFECTOS_POR_FUNCION_SECUNDARIOS`,
y `habilidad_de` da dos vueltas: primero las traducciones buenas, y solo si
ninguna función dio efecto, las de segunda vuelta. Con eso las fichas que ya
tenían efecto salen idénticas y lo único que cambia son las vacías. El recuento
lo confirma: ataque 407, crítico 203 y defensa 59 iguales; maná 150 → 187,
curar 66 → 71, ninguno 159 → 117.

### Lo que movió en el balance

Medido con el simulador, el plantel a nivel 15 (que es donde las habilidades
existen) queda **un poco más parejo**, que es lo que tenía que pasar: una
habilidad vacía era una desventaja y ahora hay 42 menos.

```
                      antes    despues
mediana               50.8%     50.1%
desviacion            17.5%     17.0%
fuera de 35-65%         140       135
```

Lo que da cada habilidad (`habilidades`) baja de 66.4% a 64.9% de media, porque
el grupo del maná crece de 30 a 38 personajes y el maná paga menos que el
ataque. Y la justicia de la guerra no se movió: una persona sola contra 6 bots gana el 16.2%, 13.8% y 16.8% en tres semillas de 600 (media 15.6%, esperado 14.3%), y antes de esto estaba en el 15-17%.

La escalera de los NPC tampoco se rompe, y era lo que había que comprobar
porque una Sombra es un espejo tuyo **con tus habilidades**: los cuatro se
siguen pudiendo ganar y ninguno es gratis.


## Esquivar, aguantar y los dos efectos negativos

**Hechos el 2026-11-09**, y lo pidió Cristopher: *"dales un uso a las
habilidades, que puedan esquivar un ataque o que apliquen debuff si es lo que
dice"*. La lista cerrada de efectos pasa de cinco a nueve.

| efecto | qué hace | valor | dura |
|---|---|---|---|
| `EVASION` | esquiva el próximo golpe que te llegue | 1 golpe | 2 turnos |
| `AGUANTAR` | un golpe mortal no te tumba | 30% de la vida | 5 turnos |
| `BAJAR_ATAQUE` | el rival pega menos | 40% | 3 turnos |
| `BAJAR_DEFENSA` | el rival recibe más | 50% | 3 turnos |

Con eso las habilidades vacías bajan de 159 a 44, y los 115 huecos que se
llenaron eran **todos** huecos: el diff contra el plantel anterior no toca ni
un nombre ni un multiplicador.

### Casi no hizo falta combate nuevo

Los dos negativos **no son una regla nueva**. Son el bono de ataque o de
defensa que ya existía, con el valor en negativo y puesto sobre otro: las dos
cuentas que ya había (`ataque_actual` y el escudo de `_danar`) los leen igual,
porque una es `1 + bono` y la otra `1 - escudo`. Lo único que hizo falta fue
un **suelo** (`SUELO_BONO`), porque sin él dos rivales turnándose podían dejar
a alguien sin pegar nada.

Esquivar y aguantar sí son dos ganchos en `_danar`, y los dos **se gastan de
uno en uno y no por turnos** (`Combatiente.gastar_bono`). Si duraran por
turnos, una evasión de dos turnos esquivaría los tres ataques de una batalla
de cuatro, y eso no es una habilidad: es ser intocable.

Y un efecto negativo **nunca se lo puede poner nadie a sí mismo**. Lo
garantizan dos sitios a la vez: `Objetivo.OTRO` en la ficha (que ya existía
para "cualquiera menos tú", así que no hizo falta un objetivo nuevo) y un
guardián en el importador, que solo acepta un efecto negativo si en FGO
apuntaba al enemigo, y solo acepta un objetivo enemigo si el efecto es
negativo. Con ese guardián se cayó una habilidad que le daba *evasión al
enemigo*, y está bien que se cayera.

### La IA tuvo que aprender que un debuff no es un regalo

`_mejor_habilidad` descartaba todo lo que apuntaba a otro, y con razón:
regalarle un beneficio a un rival en una guerra de todos contra todos es una
decisión de Master, no de una heurística. Pero un debuff también apunta a otro
y **no es un regalo, es un ataque**, así que ahora la condición mira el signo,
no el objetivo. Y el debuff va al mismo rival al que iba a atacar, que es el
que está rematando.

### Lo que la medida enseñó, que no era lo que yo pensaba

Primero les puse **menos** valor que a sus versiones en positivo, razonando
que un debuff apunta a uno y un buff te sirve contra los tres de una batalla
de cuatro. Medido, es al contrario: **un debuff tiene que dar más**, porque el
turno que gastas poniéndolo es un ataque que no haces y el bono no multiplica
ese turno.

Y hubo tres sorpresas más, todas de medir:

1. **La medida de una habilidad sola engaña.** En duelo espejo con una sola
   habilidad, `bajar_defensa` a 0.40 daba 45.8% y a 0.60 daba 70.5%. Pero la
   medida que importa es cada personaje **con su kit entero** contra sí mismo
   con esa habilidad muerta, porque una habilidad nueva no compite con no
   hacer nada: compite con las otras dos por el mismo turno. Con cuatro
   semillas (±1 punto, así que es señal y no ruido): aguantar 66.8%,
   bajar_defensa 50.4%, evasion 49.3%, bajar_ataque 41.0%.
2. **Con `bajar_defensa` a 0.60, Elisabeth Báthory ganaba el 100.0%** de sus
   duelos a nivel 15. Lleva subirse el ataque *y* bajarle la defensa al rival,
   y los multiplicadores de daño se apilan. A 0.50 nadie pasa del 91.7%. Eso
   es la regla de la casa en un ejemplo: la medida buena es la del plantel, no
   la de dos personajes.
3. **Un descuento que sonaba bien salió peor.** Le puse a `bajar_defensa` un
   0.8 en la cuenta de la IA, razonando que solo se cobra en los turnos en que
   le pegas. Los personajes que la llevan pasaron del 52.4% al 39.3%. Quitado,
   y escrito en `ai.py` para que no se vuelva a intentar sin medirlo.

### El único número puesto a sabiendas de que la IA lo juega regular

`BAJAR_ATAQUE` tiene dos medidas que se contradicen:

```
0.40 -> la habilidad rinde 41.0%   | plantel: desv 17.6%, 146 fuera, max 91.7%
0.50 -> la habilidad rinde 66.4%   | plantel: desv 18.3%, 158 fuera, max 97.2%
0.55 -> la habilidad rinde 92.9%   | la IA la prefiere a subirse el ataque
```

O sea que el valor que hace que la habilidad pague su turno es el que
desparrama el plantel y corona a alguien al 97%. Se queda **0.40**, porque la
regla de la casa desempata con el plantel, y lo que queda por arreglar no es
este número: es que la IA mide mal la mitigación. Es la misma razón por la que
defenderse es una acción débil, y está en `puntos-abiertos.md`.

### Qué movió en el balance

Los nueve efectos pagan su turno y ninguno domina (duelo espejo, nivel 15):

```
bajar_ataque  78.8%   ataque        68.5%   curar    60.7%
evasion       76.7%   bajar_defensa 65.0%   critico  59.7%
defensa       75.0%   mana          64.3%
aguantar      74.0%
```

La media de lo que dan las habilidades sigue en el 66%, igual que antes.

El plantel a nivel 15 **se ensanchó**, y era inevitable: 115 habilidades que no
hacían nada ahora hacen algo, así que el que tiene tres buenas se separa del
que tiene un hueco. Desviación 17.0% → 17.6%, y de 135 a 146 personajes fuera
de la banda 35-65%. A nivel 1 no cambia nada, porque ahí no hay habilidades.

La justicia de la guerra **no se movió**: una persona sola contra 6 bots gana
16.0%, 12.2% y 14.8% en tres semillas de 600, media 14.3%, que es exactamente
lo esperado. Y la escalera de los NPC sigue entera, que había que comprobarlo
porque una Sombra es un espejo tuyo **con tus habilidades**.

### Un objeto no puede hacer ninguna de las cuatro

`VALOR_POR_EFECTO_DE_OBJETO` no las tiene, a propósito. Un objeto no cuesta el
turno, así que un frasco que esquiva un golpe, que te levanta o que le baja la
defensa al rival sería una habilidad gratis, y estos cuatro son justo los que
peor aguantan ser gratis. Hay una prueba que lo exige.

## Quitar maná, el décimo efecto

**Hecho el 2026-11-09**, el mismo día y justo después de los cuatro de arriba,
y lo pidió Cristopher: *"Sí, añade quitar maná"*. Era el que quedaba de los
tres que `puntos-abiertos.md` daba por traducibles sin regla nueva, y el
limpio de los tres: el maná es un número y bajarlo es restar.

Traduce `lossNp` de FGO (`EFECTOS_POR_FUNCION_SECUNDARIOS`, o sea en segunda
vuelta, que es donde van las traducciones nuevas) y llega a **7 habilidades de
7 personajes**: Mephistopheles, Tamamo Cat, Tamamo-no-Mae, Hektor, Hassan of
the Serenity, Qin Shi Huang y Kriemhild. Las vacías bajan de 44 a 39.

| efecto | qué hace | valor | dura | enfriamiento |
|---|---|---|---|---|
| `BAJAR_MANA` | el rival pierde maná | 60 | — | 3 |

### Es negativo, pero no es un bono

Es el **tercer** efecto negativo y el primero que no entra por
`BONO_DEL_NEGATIVO`, porque es el espejo exacto de `MANA`, que tampoco era un
bono: los dos tocan un número y se acaban ahí. Así que `BAJAR_MANA` está en
`EFECTOS_NEGATIVOS` (apunta al rival, `Objetivo.OTRO`, y el guardián del
importador lo exige) **y** en `EFECTOS_INSTANTANEOS` (no dura turnos), y no
está en `BONO_DEL_NEGATIVO`.

Eso obligó a separar dos cosas que hasta hoy eran la misma en `ai.py`:
`_prioridad` preguntaba `hab.negativa` para ir a mirar el bono del rival, y
ahora pregunta `hab.efecto in BONO_DEL_NEGATIVO`, que es lo que de verdad
quería saber. Con `hab.negativa` habría reventado con un `KeyError`. La prueba
que lo cuida ya no exige que cada negativo tenga su bono, sino que **cada
negativo sea un bono o sea instantáneo**, que son las dos únicas formas que
tiene un efecto de existir en este combate.

Los valores también salen del espejo: 60 de maná, igual que `MANA`, y
enfriamiento 3, igual que `MANA`. No hizo falta calibrar nada, y eso es la
mitad de la gracia de un espejo.

### Lo único que la IA tuvo que aprender

Es la **única habilidad del juego que puede valer 0 por quien hay enfrente** y
no por quien la lleva: quitarle 60 a quien tiene 0 no retrasa nada. Así que
`_cuanto_paga` recibe ahora el blanco, mira `min(valor, blanco.mana)` y lo
convierte en ataques con el costo del Noble Fantasma **del rival**, que es el
reloj que se está retrasando.

### Lo que salió al medirlo

Con la medida buena (cada uno de los 7 que la llevan contra sí mismo con esa
habilidad muerta, 30 combates x 4 semillas, nivel 15):

```
bajar_mana 64.9%   (por semilla: 66.7, 63.3, 68.6, 61.0)
```

Paga su turno y no domina, y cae a un pelo del 64.3% de `mana`, que es su
espejo. De los cinco efectos del día es el segundo mejor, detrás de aguantar
(66.8%) y por delante de evasión (49.3%), bajar_defensa (48.6%) y bajar_ataque
(41.0%).

Y **no ensanchó el plantel**, que es lo que había que comprobar después del
susto de Elisabeth Báthory. Mismo plantel, nivel 15, semilla 7, con el efecto
vivo y con el efecto muerto:

```
vivo:   desviación 17.8%, 152 fuera de la banda, máximo 94.7%
muerto: desviación 17.8%, 153 fuera de la banda, máximo 92.8%
```

O sea: ni un punto de desviación y uno menos fuera de banda. El máximo lo
tiene Gareth, que **no la lleva**, así que el cambio de 92.8% a 94.7% es el
ruido de una semilla y no el efecto nuevo.

El modo `habilidades` del simulador la saca al 46.2%, pero ahí solo cayeron 2
de los 7 personajes en la muestra: con siete portadores en todo el plantel,
ese modo no tiene de dónde medir. Es justo el caso para el que se escribió la
regla de medir el kit entero.

## Ya no hay ninguna habilidad sin efecto

**Hecho el 2026-11-09**, y lo pidió Cristopher: *"llenemos las 39 habilidades
que faltan con 'quitar mana' si alguno de los personajes ya tiene esta
habilidad cambiala con la que estimes conveniente"*. Las 1044 habilidades del
plantel hacen algo.

### Lo que se puso, y dónde

Los 39 huecos estaban en 36 personajes (tres tenían dos: Musashibou Benkei,
Gilles de Rais (Caster) y Phantom of the Opera). El reparto:

- **34 se llevan quitar maná**, que es lo que se pidió.
- **5 se llevan esquivar**, que es el suplente: el segundo hueco de los tres
  personajes que tenían dos, y el hueco de los dos que **ya llevaban** quitar
  maná (Mephistopheles y Hassan of the Serenity). Dos habilidades idénticas en
  un kit de tres son una habilidad y media, porque compiten por el mismo
  turno. Se eligió esquivar y no aguantar, que rinde más, para no regalar el
  mejor efecto del plantel por un desempate.

Y va en **`data/personajes.json`**, que es donde viven los retoques escritos a
mano, no en el generado, que se sobrescribe al reimportar. Cada retoque trae
solo `efecto` y `objetivo`, así que el nombre de la habilidad y su `nombre_en`
los sigue heredando del importador. Las fichas a mano pasan de 7 a 43.

Eso obligó a reescribir la premisa de una prueba.
`test_los_retocados_a_mano_estan_completos` daba por hecho que todo el que
aparece en `personajes.json` es un personaje escrito a mano con rasgo propio;
ahora hay 36 que solo cambian el efecto de una habilidad. Lo que se exige pasa
a depender de lo que el retoque toque: el Noble Fantasma y los nombres valen
para todos, el rasgo solo para quien trae un rasgo.

### Lo que cuesta, y se asume a sabiendas

**El efecto ya no sale de lo que la habilidad dice en la obra.** Hasta hoy la
regla era que del dato sale *qué* efecto tiene y del juego *cuánto* da; estas
39 rompen la primera mitad. Nueve de ellas decían en FGO "no actúas este
turno" y ahora quitan maná, que no es lo mismo ni se parece. Lo que lo hace
tolerable es que el efecto elegido sí es un efecto del juego, con sus valores
de siempre, y que está escrito en `personajes.json`, donde se ve: no hay una
regla nueva escondida en el código.

A cambio, lo que se gana es que **ninguna habilidad gasta el turno a cambio de
nada**. Una habilidad vacía se le ofrecía al jugador en el menú de combate y
la IA nunca la usaba (`ai._cuanto_paga` devuelve 0 para `NINGUNO`), así que
era una trampa que solo pisaban las personas. Eso era el primer punto abierto
y ya no existe.

### Qué movió en el balance

El plantel a nivel 15 **se juntó**, que era lo esperado: el que llevaba un
hueco inútil ahora lleva algo, así que los de abajo suben.

```
antes:   desviación 17.8%, 152 fuera de la banda 35-65%, máximo 94.7%
después: desviación 17.6%, 149 fuera de la banda 35-65%, máximo 91.7%
```

**Quitar maná rinde menos ahora que lo llevan 41 y no 7**: pasa del 64.9% al
**54.0%** (cada portador contra sí mismo con esa habilidad muerta, 30 combates
x 4 semillas, nivel 15; por semilla 53.1, 54.7, 54.4, 53.9). Sigue pagando el
turno que cuesta, pero con poco margen, y eso tiene sentido: los 7 primeros
eran personajes cuyo kit la aprovechaba, y los 34 nuevos la llevan porque
había un hueco. Esquivar queda igual (48.1% con 28 portadores, 49.3% con 23).

La justicia de la guerra **no se movió**: una persona sola contra 6 bots gana
12.5%, 13.8% y 14.3% en tres semillas de 600, media **13.5%** contra el 14.3%
esperado, dentro de la desviación de ±1.1 puntos que tiene esta medida. (Con
quitar maná recién puesto y antes de llenar los huecos había salido 14.9%.) Y
las guerras siguen durando 3.9 días.

Y una medida que **no hay que leer como un cambio de balance**: `bajar_ataque`
sale al 33.2% cuando antes salía al 41.0%. Tres de sus 13 portadores tenían
huecos (Gilles de Rais, Jeanne d'Arc, Fuuma Kotarou) y ahora tienen otra
habilidad compitiendo por el turno, así que el "con" y el "sin" de la medida
cambiaron para ellos. Con 13 personajes eso mueve ocho puntos. El problema de
fondo sigue siendo el de siempre (la IA mide mal la mitigación, punto 1.b de
`puntos-abiertos.md`) y no este cambio.

## Cinco preguntas abiertas, contestadas

**El 2026-11-10**, repasando `puntos-abiertos.md`. Cristopher contestó cinco de
una vez, y dos de las respuestas fueron *dejarlo como está*, que también es una
decisión y por eso están aquí.

### 1. El Noble Fantasma que nadie sabe cómo se llama: fuera de la ficha

Atlas Academy tapa con interrogantes lo que en FGO es un secreto de la
historia. **Siete** personajes traían el nombre como `???` y el rango como
`？` (Moriarty, Scheherazade, Wu Zetian, Penthesilea, Columbus, Tomoe Gozen y
Mochizuki Chiyome), y el jugador leía "**???** (rango ？)". Otros dos traen
tapado solo el tipo (Emiya y Arthur Pendragon (Prototype)), y da igual, porque
el tipo no se enseña.

*(Antes decía nueve. Eran nueve fichas con algo tapado y siete con el nombre
tapado, que es lo único que se ve.)*

Se eligió esconderlo, que es lo práctico: escribir siete nombres a mano es
inventarse datos de la obra. Un nombre tapado **se limpia al leerlo**
(`noble_fantasma_desde`, con `MARCAS_TAPADAS`), el rango se va con él porque
un rango sin nombre no es información, y la ficha dice "Nombre desconocido"
seguido de lo que hace.

Lo que **no** cambia: el Servant tiene Noble Fantasma y lo lanza igual. Eso
obligó a tocar una línea sutil: `NobleFantasma.__bool__` miraba el nombre, y
ahora mira `nombre or oculto`. Si no, uno tapado habría pasado por "no tiene",
que es lo que significa `SIN_NOBLE_FANTASMA` y lo que llevan las Sombras.

### 2. Las monedas en `/estado-guerra`: se queda como está

El oro y los griales se ven en la tienda y el inventario, y ahí se quedan. No
hacía falta: el botón del menú ya lleva el oro en la etiqueta.

### 3. `/mi-cuenta`, el único comando que no necesita una guerra

Los griales viven en `tienda.Cuenta`, que es lo único del juego que **no**
cuelga de una guerra, y hasta hoy no había dónde mirarlos si no estabas en
una. `/mi-cuenta` (`/my-account`) dice los griales y las guerras ganadas, en
privado, y funciona en un canal sin guerra: el idioma lo pone Discord cuando
no hay guerra que lo diga. A quien no ha ganado ninguna le explica cuándo se
reparte el Grial, que es la pregunta que va a tener.

### 4. Rendirse, y por qué no paga Grial

Hasta hoy una guerra se acababa para todos o para nadie. Ahora hay un botón
**Rendirse** en el menú, rojo y al final, que **pide pulsarlo dos veces**: el
primer clic cambia la etiqueta a "¿Seguro? Pulsa otra vez" y el segundo lo
hace. No hay vuelta atrás.

Lo que lo hizo barato es que no hizo falta ninguna regla nueva:
`Master.eliminado` ya era la pregunta que se hacía todo el código ("¿está
fuera?"), y ahora mira las dos vías, perder y rendirse. Así, el que se rinde
deja de estar en `activos` y con eso solo: no entra en las batallas que se
forman, no se le espera para cerrar el día y no puede ganar. El campo
`retirado` **sí** se guarda en la base de datos, al contrario que `cancelada`:
si no, un reinicio devolvería a la guerra al que se fue.

Si se rinde con una batalla en curso, su Servant no cae ni pierde: se le quita
de los que deciden a mano y **la IA juega su mano**, igual que cuando alguien
no contesta en cinco minutos (`dia.rendir_en_combates`). Ya está fuera de la
guerra, así que cómo acabe esa batalla no cambia nada para él; lo que importa
es que los demás puedan terminarla. Y si era el único que decidía, la batalla
se juega sola hasta el final, porque si no el día se quedaría colgado hasta
que venciera el plazo del turno.

**Si todos se retiran, el último en pie gana la guerra**, que es lo que pidió
Cristopher. El Grial es otra cosa: lo propuse a cero y Cristopher lo puso en su
sitio, **se cobra solo si se unieron más de 5 personas**
(`MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA = 6`, contra el mínimo normal de 4).

El razonamiento es de cuánto cuesta hacer trampa. Con el mínimo de 4, tres
personas de acuerdo coronan a la cuarta el día 1 y se reparten un grial por
guerra, que es *exactamente* lo que `gana_el_grial` existe para impedir.
Pidiendo 6 hay que juntar a seis personas de verdad para farmear un grial, y
eso ya es más trabajo que jugar la guerra. Mi versión (nunca) era más segura y
peor: castigaba a la guerra de siete en la que la gente se va de verdad.

Lo lleva `Guerra.acabo_por_retirada`, que se pone cuando una retirada deja a
uno solo, y `gana_el_grial` lo cruza con cuántas personas se apuntaron. **Una
retirada en una guerra que después se pelea no anula nada**: si de cuatro
personas una se va y las otras tres se eliminan peleando, el Grial se paga;
hay prueba de los tres casos (4 se van: no; 5: no; 6: sí).

### Esto creó el segundo sitio que paga griales, y casi se me escapa

Hasta hoy la regla era que **los griales se pagan en `narrar_cierre` y solo
ahí**, porque era el único sitio que anunciaba el Grial. Una guerra que acaba
por retiradas no pasa por ahí: la cierra `rendir_al_master`. Así que si el
Grial puede cobrarse por ese camino, ese camino tiene que pagarlo, o el
ganador leería en el canal que ganó un grial que no está en su cuenta. Ahora
son dos sitios, los dos llaman a `pagar_los_griales`, y está escrito en los
dos.

Y buscándole las vueltas apareció un fallo de verdad, que encontró una prueba:
`Guerra.rendirse` devolvía `self.terminada` cuando el Master ya estaba fuera,
y como el pago mira esa respuesta, **rendirse otra vez después del final
pagaba el Grial otra vez** (de 2 griales a 4). Ahora devuelve `False`: lo que
contesta es "esta retirada acabó la guerra", y quien ya estaba fuera no acaba
nada.

Y al canal solo va quién se retiró y cuántos quedan. Ni un Servant, ni una
habilidad, como todo lo que sale al canal.

### 5. Comercio entre Masters: no

Regalar o vender objetos y monedas entre Masters queda descartado, no
aplazado. El motivo es el que ya estaba escrito en `puntos-abiertos.md`: un
pacto deja de ser verbal si puedes pagarlo, y lo que hace jugables los pactos
hoy es justo que no se pueden garantizar. Lo que sí sigue en pie es poder
darle un beneficio a cualquiera de tu batalla, que es un pacto que se cumple
en el momento o no se cumple.


## Los Sellos de Comando

*2026-11-10.* Llevaban desde el principio en la ficha del Master (`sellos`, 3
por cabeza, 5 en la de Jeanne), guardados en la base de datos, y **no hacían
nada**: el único uso confirmado era llenar la barra de maná y los demás estaban
propuestos sin cerrar (curar, dar una acción extra). Cerrados y construidos.

### Qué hacen: tres usos y una lista cerrada

| Sello | Qué hace | De dónde sale |
| --- | --- | --- |
| Llenar el maná | La barra queda en el costo del Noble Fantasma | Regla propia, dos líneas |
| Curar | +40% de la vida máxima | El efecto `CURAR` de los diez, por `_aplicar_efecto` |
| Habilidades listas | Apaga los enfriamientos | Regla propia, una línea |

Que la lista sea **cerrada** (`sellos.Uso`) es lo mismo que hace un rasgo con
sus perillas: así un Sello no puede inventar una regla de combate. Y por eso
hay una prueba que falla si algún día son cuatro sin que nadie lo decida.

Solo uno de los tres pasa por un efecto de los diez, y el documento lo dice
en vez de disimularlo: llenar la barra no es sumar maná (es ponerla al costo
del Noble Fantasma, sin pasarse) y apagar un enfriamiento no es un bono de
nadie. Son dos reglas nuevas de tres líneas en total, y la alternativa —
forzarlas a parecer efectos— habría sido peor.

### La forma está copiada del objeto; lo que cambia es el precio

Un Sello **no gasta el turno**, igual que un objeto: usarlo no es tu decisión,
pasa antes de elegirla, y después sigues teniendo que elegir. No da maná y no
se enfría. El menú de combate deja su botón encendido aunque ya hayas decidido,
por lo mismo que el de los objetos.

Lo que cambia es de dónde viene el tope, y es toda la economía del Sello:

- un objeto se compra con oro y el tope es **uno por batalla**;
- un Sello no se compra en ninguna parte: son **tres para toda la guerra**, y
  encima **uno por batalla**.

Por eso un Sello puede dar más que una habilidad aunque no cueste el turno: el
precio no es el turno, es que te queden dos. La habilidad de curar da el 12% de
la vida máxima y gasta el turno; el Sello da el 40% y no gasta nada, y es la
tercera vez en toda la guerra.

**El tope de uno por batalla no es decoración.** Sin él, los tres Sellos de la
guerra se gastan en el mismo turno (llenar la barra, curarse y repetir la
habilidad buena a la vez), y tres decisiones repartidas por cuatro días se
convierten en una. Con él, cada batalla te pregunta como mucho una vez.

### Dónde viven los dos topes, y por qué ahí

En el `Master`, los dos: `sellos` (los de la guerra) y `sellos_en_la_batalla`
(el de hoy). **Una batalla no sabe de Masters**, igual que no sabe de
inventarios, así que `Combate.usar_sello` no comprueba ninguno de los dos: lo
hace el Cog antes de llamar, exactamente como con los objetos. Y se descuentan
juntos, en `Master.gastar_sello`, porque por separado cada uno deja de existir:
bajando solo `sellos` desaparece el tope por batalla, y bajando solo el otro
los Sellos son infinitos.

De los dos contadores, **el de la guerra se guarda en la base de datos y el de
la batalla no**, que es la misma asimetría que tenía el inventario
(`usados_en_la_batalla` tampoco se guarda). Es deliberado: lo que no puede
pasar es que un reinicio te devuelva un Sello gastado, y una batalla dura
minutos.

### Lo que un Sello no hace: una acción extra

Estaba propuesto en los documentos y se descarta. Un turno se resuelve con las
decisiones de todos a la vez (`battle.resolver_turno`), así que "actúas otra
vez" no es un efecto: es un turno dentro de un turno, y eso es una regla nueva
en el motor, de las que la casa evita. Llenar la barra de maná es la versión de
esa idea que sí cabe sin tocar nada: no te da un turno de más, te deja gastar
el que ya tienes en el Noble Fantasma, que es lo que de verdad se quería.

### Lo que queda sin medir, dicho de frente

`CURACION_DEL_SELLO` (0.40) es un **número razonado y no medido**, y es el
segundo del combate en esa situación después de
`VALOR_POR_EFECTO_DE_OBJETO`. La razón es la misma: la IA no gasta Sellos, así
que el simulador no puede decir si están bien. Aquí es un poco peor que con los
objetos, porque los bots **sí tienen** tres Sellos cada uno y no los gastan
nunca, así que una persona que los use tiene una ventaja que no está medida.

Lo que sostiene el número mientras tanto no es una medida, es que ninguno de
los tres usos puede romper el combate por sí solo: llenar la barra adelanta un
Noble Fantasma que iba a llegar de todas formas, curar no pasa de la vida
máxima, y apagar los enfriamientos no mueve ningún número. Está anotado en
`puntos-abiertos.md`, junto al de los objetos y con la misma cura: enseñar a
`ai.py` a usarlos.
