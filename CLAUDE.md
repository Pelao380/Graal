# Graal

Bot de Discord para jugar guerras del santo grial al estilo de Fate: 7
Masters invocan un Servant cada uno y pelean hasta que queda uno solo.
Python con discord.py y SQLite. Proyecto de fans, sin monetización y sin arte
oficial.

**Lee primero** `docs/reglas-graal.md` (las reglas del juego, que son la
especificación), `docs/decisiones.md` (lo cerrado y por qué) y
`docs/puntos-abiertos.md` (lo que falta). Esos tres archivos son la fuente de
verdad: si el código los contradice, el código está mal.
`docs/como-jugar.md` es la versión para jugadores, resumida y sin jerga de
Fate; no es fuente de verdad, pero si una regla cambia hay que repasarlo.

## Reglas de la casa

**La lógica del juego no sabe nada de Discord.** Todo `bot/src/game/` se puede
probar y simular sin token, sin red y sin encender el bot. Solo `bot/src/bot.py`
y `bot/src/commands.py` importan discord.

**Los plazos van en la base de datos, nunca en memoria.** Una guerra dura días
y el bot se va a reiniciar. Hay una tabla `plazos` para eso, y al arrancar se
revisa `db.plazos_vencidos()`.

**Las guerras se guardan en `src/repositorio.py`, enteras y de una vez.** El
Cog las lee en `cog_load` y llama a `self.guardar(guerra)` al final de cada
método compartido que cambia algo (`texto_invocacion`, `texto_listo`,
`pelear_npc`, `textos_del_cierre`, `arrancar`) y de los dos comandos del lobby.
**Si añades una acción que cambie algo, llama a `guardar`**: nada te va a
avisar. Un Servant se guarda por `collection_no`, no por nombre, porque los
nombres no son únicos.

**Los personajes viven en datos, no en código.** `bot/data/personajes_generados.json`
son los 348 derivados del export de Atlas Academy: **no se edita a mano**, se
sobrescribe al reimportar con `python tools/importar_servants.py`. Los retoques
escritos a mano van en `bot/data/personajes.json`, que se aplica encima
emparejando por `collectionNo`, y solo necesita traer lo que cambia.

**El presupuesto de estadísticas es sagrado.** Los tres multiplicadores de cada
personaje suman 3.00 y ninguno sale del rango 0.55–1.35. Se valida al cargar.
Si un personaje no cuadra, no entra.

**Un rasgo solo puede mover las perillas definidas en `personajes.py`.** Así un
personaje nuevo no puede inventar una regla que rompa el combate.

**Un objeto es una habilidad que no cuesta el turno, y por eso da menos.**
Los objetos viven en `bot/data/objetos.json` (este sí se edita a mano) y usan
los mismos cinco efectos del combate, así que `battle.py` no necesitó ninguna
regla nueva. Del dato sale **qué** efecto tiene; **cuánto** da lo decide
`VALOR_POR_EFECTO_DE_OBJETO`, a dos tercios de la habilidad del mismo efecto.
Lo que lo sostiene es el tope de **uno por batalla**, y ese tope vive en
`Master.inventario`, no en `Combate`: una batalla no sabe de inventarios, así
que lo comprueba el Cog antes de llamar. Los objetos duran la guerra y se
guardan en la columna `inventario` de `masters`; lo único que vuelve a cero
con el día es `usados_en_la_batalla`. **Usar un objeto no es la decisión del
turno**: después sigues teniendo que elegir tu acción. Y el texto nombra el
objeto, así que va efímero y al canal no llega nada.

**Un Sello de Comando es un objeto que no se compra, y por eso da más.** Los
tres usos viven en `game/sellos.py` y son una lista cerrada (`Uso`): llenar el
maná, curar y apagar los enfriamientos. Como el objeto, **no gasta el turno**;
al contrario que el objeto, no se vuelve a comprar: son **tres en toda la
guerra** y **uno por batalla**. Los dos topes viven en el `Master` (`sellos`,
que se guarda en la base de datos, y `sellos_en_la_batalla`, que no y vuelve
con el día), los comprueba el Cog antes de llamar a `Combate.usar_sello`, y se
descuentan **juntos** en `gastar_sello`: por separado, cada uno de los dos
topes deja de existir. Solo curar pasa por `_aplicar_efecto`; los otros dos no
son ninguno de los diez efectos y los resuelve `battle.usar_sello`. Y **no hay
Sello de acción extra** a propósito: un turno se resuelve con todas las
decisiones a la vez, así que eso sería una regla nueva del motor.
`CURACION_DEL_SELLO` es, con `VALOR_POR_EFECTO_DE_OBJETO`, la otra constante de
combate sin medir, porque la IA no gasta Sellos.

**Hay dos monedas y duran distinto, y eso es toda la economía.** El **oro**
vive en `Master.oro`, lo da ganar NPC y batallas y **muere con la guerra**;
compra objetos. Los **griales** viven en `tienda.Cuenta`, tabla `cuentas`
(la única que no cuelga de `guerras`), los da ganar una guerra y **se quedan en
la cuenta**; compran catalizadores. Si el oro sobreviviera, una guerra nueva no
empezaría empatada. **Los griales se pagan por `guerra.gana_el_grial()` y nunca
por `ganador()`**: eso es lo que impide farmearlos contra bots, porque hacen
falta 4 personas de verdad. Se pagan en los **dos** sitios que anuncian el
Grial, y solo en esos: `narrar_cierre` (la guerra se acaba peleando) y
`rendir_al_master` (se acaba porque los demás se retiraron, y entonces hacen
falta más de 5 personas). Si añades un tercer sitio que lo anuncie, tiene que
llamar a `pagar_los_griales`, o alguien leerá que ganó un grial que no tiene. **`guardar(guerra)` no salva los griales**: la cuenta se
guarda con `apuntar_cuenta` y hay que acordarse. Y el orden de una compra es
siempre **comprobar, cobrar, entregar**: con el inventario lleno no se cobra.

**Una habilidad hace una sola cosa, de una lista cerrada.** Los **diez**
efectos están en `personajes.py` y son las perillas que el combate ya tiene:
los cinco de siempre (ataque, defensa, crítico, mana, curar) y los cinco del
2026-11-09 (esquivar un golpe, aguantar uno mortal, y bajarle el ataque, la
defensa o el maná al rival, que son **los tres únicos efectos negativos**); el importador traduce los `funcType` y
`buff` de FGO a ellos y descarta el resto. **Del personaje sale qué efecto
tiene cada habilidad; cuánto da lo decide el juego**, en
`VALOR_POR_EFECTO`/`TURNOS_POR_EFECTO`, y el enfriamiento también sale del
efecto. Las magnitudes de FGO se descartan a propósito: están hechas para un
juego donde usar una habilidad no cuesta el turno.

**Se dice Master y Servant**, como en la serie: en lo que ve el jugador, en los
documentos y en el código (`Master`, `Servant`, tablas `masters` y `servants`).
El resto del código sigue en español.

**Ninguna frase que lea el jugador se escribe en el código.** Todas viven en
`bot/data/textos.json`, en español y en inglés, y se piden con
`game.textos.t("clave", idioma, ...)`. Se valida al cargar: si a una clave le
falta un idioma o sus huecos no cuadran, revienta al arrancar. El idioma lo
elige quien crea la guerra y lo llevan dentro la `Guerra` y la `Batalla`.

**El idioma por defecto es el inglés** (`IDIOMA_POR_DEFECTO`, en `textos.py`):
lo usan la guerra creada sin elegir, los nombres de comando que ve quien tenga
un idioma que no tenemos, y cualquier `t()` sin idioma. El español es una
traducción más.

**Hay dos idiomas en juego y no son el mismo.** Lo que el bot **responde** va
en el idioma de la guerra; el **nombre de un comando** (`/create-war` o
`/crear-guerra`) lo decide el idioma de Discord de quien mira, porque se
escribe antes de que exista la guerra. Los nombres y las ayudas salen de las
claves `cmd.*` a través del `Translator` de `commands.py`, que se engancha
antes de sincronizar.

**El Servant ajeno es secreto hasta que peleas con él.** Lo decide
`Master.conoce(id)`, y `texto_estado(guerra, quien=None)` **no revela nada por
omisión**: si añades un sitio que lo llame, pásale quién mira o no verá
Servants. Por eso `/estado-guerra` es privado y por eso el detalle de una
batalla no se publica en el canal, solo lo lee cada participante desde su menú
(`Master.ultimo_registro`): las frases nombran las habilidades y eso delata al
Servant. **Si añades un mensaje al canal, no nombres un Servant ni una
habilidad.**

**No se toca un número de balance sin medirlo.** Todas las constantes de
combate están calibradas con el simulador y llevan en el comentario qué se
midió y qué salió. Antes de cambiar una, córrelo; después, córrelo otra vez.
Medir contra el plantel completo da respuestas distintas a medir dos
personajes: la buena es la del plantel.

**El token nunca va en el código ni en el repositorio.** Va en `bot/.env`.

**El arte oficial se puede tener en local, pero el bot no lo publica.**
**El bot enlaza el arte, no lo sube.** La ficha lleva un `discord.Embed` con
`set_image(url=...)` apuntando a Atlas Academy (`Servant.imagen`): el bot manda
un enlace y la imagen la pide el cliente de quien mira. Subir el archivo
(`discord.File`, `discord.Attachment`) dejaría una copia del arte en el CDN de
Discord servida por nosotros, y eso no se hace. `tests/test_arte.py` falla si
alguien cruza esa línea, a propósito: cruzarla tiene que ser una decisión y no
un descuido, así que primero se cambia `docs/decisiones.md`. Y va siempre en
mensaje **efímero**, porque enseñar un Servant en el canal delataría quién
lleva qué: se enseña al invocar, en la ficha y en los Servants que conoces, y
en el canal nunca. `arte_del_servant()` devuelve `None` sin Servant y sin URL,
así que se puede llamar sin comprobar nada antes. Qué arte le toca lo dice `Servant.ascension` (1-4, 5-9, 10-14, 15),
los mismos cortes que `NIVELES_HABILIDAD` y contados desde ahí: el aspecto
cambia justo cuando se desbloquea una habilidad. La copia local de
`data/imagenes/` (con `tools/descargar_imagenes.py`, y en `.gitignore`) es
para mirar el plantel, no alimenta al bot. Lo que sí se usa son los datos: las
estadísticas y los nombres son información **sobre** la obra, el arte **es** la
obra.

**Antes de modificar un archivo, se guarda como estaba en
`.respaldo/<AAAA-MM-DD>/`.** Una subcarpeta por día, la copia se hace antes del
primer cambio del archivo en la sesión y no se sobrescribe después (la primera
es la buena). La carpeta está en `.gitignore`. Esto existe porque el 2026-11-07
siete archivos volvieron solos a su versión de dos días antes y, sin
repositorio git, la única fuente fue la transcripción de la sesión. El respaldo
es una red local, no historial: sigue pendiente hacer `git init`.

## Comandos

Desde `bot/`:

```bash
.venv\Scripts\python -m unittest discover -s tests -t .   # 628, sin token ni red
                                              # con `python` suelto se saltan
                                              # 105: discord.py esta en el venv
python tools/comprobar_bot.py                 # revisa el .env y carga el bot
python tools/ver_db.py                        # abre graal.db y lista las tablas
python -m src.simulator --semilla 7 niveles   # cuánto decide el nivel
python -m src.simulator --semilla 7 plantel   # busca personajes rotos
python -m src.simulator --semilla 7 triangulo # matriz de emparejamientos
python -m src.simulator --semilla 7 npc       # la escalera de entrenamiento:
                                              # victorias y XP por dia y nivel
python -m src.simulator --semilla 7 habilidades  # si pagan el turno que cuestan
python -m src.simulator --semilla 7 guerras   # guerras enteras, con bots o sin ellos
python -m src.simulator --semilla 7 economia  # cuanto oro da una guerra y que compra
python tools/ver_batalla.py                   # el registro de una batalla,
                                              # con la IA a los dos lados
python tools/importar_servants.py             # regenera el plantel
python tools/descargar_imagenes.py            # el arte, a data/imagenes/:
                                              # 1396 imagenes, ~0.74 GB, copia
                                              # local y nunca al repositorio
python -m src.bot                             # arranca el bot (necesita .env)
```

Pasa siempre `--semilla` al simular, para que dos corridas sean comparables.

## Trampas conocidas

- Los nombres de los personajes son los de la versión americana: es "Altria",
  no "Artoria", y "Emiya" sin mayúsculas.
- Los nombres **no son únicos**: hay dos Cú Chulainn, tres Medusa. La clave es
  `collectionNo`. Los repetidos se desambiguan añadiendo la clase.
- **`collectionNo` 0 significa "no se invoca"**, y el importador lo descarta.
  Un Servant sin cupo en la colección no es jugable: el caso que lo descubrió
  es Hyde, que venía como `type` "normal" pero es la forma Berserker de
  Jekyll, que ya está en el plantel con el número 81. Tenerlo era tener a
  Jekyll dos veces, y sus cuatro URLs de arte daban 404. Por eso el plantel
  son 348 y no 349.
- Defender es una acción débil: da mana, pero el mana solo sirve para el Noble
  Fantasma. Prohibirle defenderse a un personaje es un beneficio, no un
  castigo. Se midió (antes de que el Noble Fantasma se pudiera repetir; con
  eso el mana vale más, así que esta medida habría que rehacerla).
- **El Noble Fantasma no tiene tope**: se repite cada vez que se junten los
  100 de mana. Tuvo tope de uno por combate y era un error de fondo, no de
  número: como todo el mundo llegaba a 100 en el turno 6 de un combate de 10,
  el mana no escaseaba, y en cuanto lo soltabas dejaba de valer nada. Las
  habilidades de mana (147 de 349 personajes) costaban más de lo que daban.
  Si vuelves a tocar `COSTO_NOBLE_FANTASMA` o `MANA_POR_ATAQUE`, la pregunta
  que importa es **si llegar a 100 sigue siendo una decisión o vuelve a ser un
  reloj**.
- **El factor de dificultad de los NPC es un dial horrible.** Las victorias
  del jugador van del 100% con factor 0.80 al 49% con 1.00 y al 14% con 1.03:
  los últimos tres centésimos valen 34 puntos. La banda útil es 0.85–1.00 y
  hay un `FACTOR_MAXIMO` de 0.99 para que el endurecimiento por día no cruce
  el 1.00, porque cuando lo cruzaba el 4.º NPC pasaba del 84% el día 3 al 5%
  el día 7. **Una Sombra nunca puede ser un espejo más fuerte que tú.**
- **Una Sombra sí lanza Noble Fantasma.** `SIN_NOBLE_FANTASMA` solo le quita
  el nombre en la ficha; `puede_noble_fantasma` mira el mana y nada más. Si
  alguna vez quieres que de verdad no tenga, hay que gatear la acción en
  `battle.py`. Me equivoqué con esto y me costó un diagnóstico entero.
- **La medida de justicia (`guerras`) necesita varias semillas, no una corrida
  más larga.** Con `-n 600` llegó a tener ±2.7 puntos de desviación entre
  semillas: una persona sola contra 6 bots salió 11.8%, 12.5%, 12.8%, 14.7% y
  18.5%, cuando le toca el 14.3%. Un solo número no distingue un cambio de
  balance del ruido; la media de 5 semillas x 600, sí. (Desde que los NPC se
  endurecieron la desviación bajó a ±1.1 puntos, porque el combate depende
  menos de la suerte, pero la costumbre de correr varias semillas se queda.)
- Usar una habilidad cuesta el turno entero: un ataque **y** sus 15 de mana, o
  sea retrasar el Noble Fantasma. Por eso una habilidad da 10 de mana y los
  bonos son grandes (x2.5 al ataque, 35% a la defensa), y por eso la IA mide
  todo en "ataques" y no las encadena. Medido: con los valores de FGO tal cual
  y una IA que las usaba sin medir, el que las tenía perdía el 92% de los
  duelos espejo.
- Las medidas del plantel a nivel 1 y a nivel 15 dicen cosas distintas, porque
  a nivel 1 no hay habilidades. Pasa `--nivel 15` al simulador cuando lo que
  mides tenga que ver con ellas.
- El orden en que se declaran los ataques **no** decide nada: cuando una
  cadena pasa de 4, `formar_batallas` sortea quién entra, y al que no cabe le
  busca otro rival. Antes decidía el orden, y eso valía del 10% al 27% de
  victorias para el mismo jugador según si declaraba primero o último. Si
  alguna vez vuelve a depender del orden, la medida hay que hacerla con las
  declaraciones intercaladas al azar.
- **El reloj de la guerra es `Guerra.reloj`**, no `time.time()` suelto. Para
  probar un plazo se le pone un reloj de mentira y las 24 horas pasan en una
  línea; si alguna vez miras la hora directamente, esa prueba hay que esperarla.
- **El día se cierra en `game/dia.py` y solo ahí, y son dos mitades.**
  `abrir_combates()` acaba la preparación (invoca por quien falte, forma los
  grupos) y deja las batallas **en curso**, en `Fase.BATALLA`; las de puros
  bots salen ya resueltas. `cerrar_combates()` pasa al día siguiente, y lo
  llama **la última decisión de la última batalla**, no un comando.
  `cerrar_dia()` sigue ahí y hace las dos cosas de corrido con la IA: lo usa
  el simulador, una guerra sin personas peleando y el vigilante. **Las dos
  formas tienen que dejar la misma mesa** y hay una prueba que lo exige.
  `puede_cerrar()` exige que todas las personas vivas esten `listo`; abrir los
  combates no comprueba nada, porque el vigilante tiene que cerrar el dia
  aunque falte gente.
- **Lo que no se puede olvidar al acabar una batalla está en
  `anotar_batalla()`**, que llaman los dos caminos: quién vio qué Servant y
  las derrotas. `recoger()` es idempotente a propósito porque lo llama cada
  decisión; si una batalla se anotara dos veces, una derrota contaría doble.
- **En una batalla puede caer más de uno**, así que `BatallaDelDia` lleva
  `caidos` y `eliminados` en plural. La batalla se acaba cuando cae el
  primero, pero si quedan dos o más en pie y alguien vota por seguir, se
  sigue. Apuntar solo `caidos[0]` era un error que duró semanas, en `dia.py`
  **y en el simulador**: el que caía en el turno especial salía gratis.
- **Hay cuatro puertas por las que se cierra un dia y todas pasan por
  `cog.cerrar_el_dia`**: `/empezar-batallas` (`_contar_cierre`), el boton rojo
  del menu (`MenuAccion.boton_batallas`), **decirse listo el ultimo**
  (`MenuAccion.boton_listo`, si `puede_cerrarse_ya`) y el vigilante de plazos.
  Lo unico que cambia entre ellas es por donde se habla, y se pasa como
  argumento: `enviar_por(interaction)` o `enviar_por_el_canal(canal)`. **No
  escribas una quinta puerta a mano**: llama a `cerrar_el_dia`. Cerrar la
  preparacion es solo la mitad; la otra es **dejar el boton que toque en el
  canal**: el de abrir tu combate si hay batallas, el del menu si empieza un
  dia nuevo, o ninguno si la guerra acabo. Eso lo decide
  `aviso_y_vista_de_despues()` y nada mas.
  Si el dia se puede cerrar lo pregunta `puede_cerrarse_ya()`, que llama al
  mismo `aviso_si_no_se_puede_cerrar()` que el boton rojo: si preguntaran
  cosas distintas habria dias que no cierra ninguno de los dos.
- **Un menu efimero puede ser de ayer.** `MenuAccion` nace con
  `dia_del_menu` y `boton_listo` se niega si la guerra ya va por otro dia:
  desde que decirse listo cierra el dia, pulsarlo en un menu viejo cerraba el
  dia nuevo **sin haberlo jugado**, sin entrenar y sin declarar. Lo encontro
  una prueba, no una partida.
- **Cerrar la preparacion no siempre deja `Fase.BATALLA`.** Si al humano le
  toco descansar, las batallas son todas de bots, salen ya resueltas y el dia
  se cierra entero: la fase vuelve a `PREPARACION`, pero del dia siguiente. Y
  a quien le toca pelear depende del orden en que se recorren los Masters, que
  **cambia de una corrida a otra** (Python aleatoriza el hash de las cadenas),
  asi que una prueba que exija una de las dos salidas falla una de cada tres
  veces. Exige "el dia se acabo" (`_acabo_el_dia_1`).
- **Un turno se resuelve con la decisión del último, así que a los demás hay
que ir a buscarlos.** `Combate.decidir` solo le devuelve los eventos a quien
cerró el turno; el resto se quedaba sin ver nada. Eso lo arregla
`repartir_el_turno`, con `self.mesas` (la última interacción de cada uno, que
vale 15 minutos): les reescribe el menú **y** les manda el turno, porque un
mensaje editado no notifica. Solo a los de `combate.humanos` de **esa** batalla
y siempre en privado, que el registro nombra habilidades. Cada camino del menú
de combate llama a **`despues_de_decidir`** y a nada más: ahí viven juntas las
dos cosas que se olvidan solas (repartir el turno y cerrar el día).

**Una batalla en curso vive en memoria** (`self.combates` del Cog), al
  contrario que los plazos: dura minutos, no dias. Lo que salva a la guerra de
  quedarse parada en `Fase.BATALLA` tras un reinicio es `dia.recuperar_dia()`,
  que lo llama el vigilante y usa `ultimo_registro_dia` para no repetir una
  batalla ya peleada.
- Estar `listo` cierra el dia de quien lo dice: despues no entrena **ni cambia
  de objetivo** (`motivo_para_no_planear`, que usan el boton para apagarse y
  la accion para explicarse). Si se
  pudiera entrenar despues, el creador entrenaria, cerraria el dia y a los
  demas les quedaria el 2.7% de victorias en vez del 15%. Se midio.
- **`empezar()` no reparte los Servants**, solo los sortea y los deja en
  `sin_repartir`; cada Master pide el suyo con `invocar_para()` durante el día
  1, y `formar_batallas()` invoca por los que falten antes de armar nada. Una
  prueba que necesite a los siete con Servant usa el ayudante `_empezar()` de
  `tests/test_war.py`, no `Guerra.empezar` a secas.
- **El día de los bots lo abre la guerra, no el bot de Discord.**
  `Guerra.abrir_dia()` los entrena y declara sus ataques, y la llaman
  `empezar()` y `siguiente_dia()`. No la llames desde `commands.py`: si
  dependiera de que alguien escriba un comando, el día que el jugador no
  apareciera sus rivales se quedarían al nivel 1. Durante un tiempo esas dos
  cosas solo las llamaba el simulador y en Discord los bots no entrenaban.
- El modo `guerras` del simulador necesita `-n` grande: con las 60 por defecto,
  una persona sola contra 6 bots salió al 5% cuando le toca el 14.3%, y eran
  tres guerras de sesenta. Con `-n 600` sale 15.8%.
- Los volcados crudos (`bot/data/*_servant.json`) están en `.gitignore` y se
  regeneran. Si una descarga se corta, el JSON queda sin cerrar: un export
  completo termina en `]`.
- **Hay dos formas de quedarse fuera de una guerra y las dos pasan por
  `Master.eliminado`**: dos derrotas o rendirse (`Guerra.rendirse`, el boton
  rojo del menu, que pide pulsarlo dos veces). Por eso anadir rendirse no
  necesito ninguna regla nueva: todo lo que preguntaba "esta fuera" lo
  pregunta igual. **`retirado` si se guarda en la base de datos**, al
  contrario que `cancelada`: si no, un reinicio devolveria a la guerra al que
  se fue. Y el que gana porque los demas se retiraron cobra el Grial **solo si se
  unieron mas de 5 personas** (`Guerra.acabo_por_retirada` y
  `MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA`, 6 contra el minimo normal de 4):
  con 4 bastaria que tres se pusieran de acuerdo para coronar a la cuarta el
  dia 1. Y ojo con lo que devuelve `rendirse`, que es "esta retirada acabo la
  guerra" y no "la guerra esta acabada": devolver lo segundo hacia que
  rendirse despues del final pagara el Grial dos veces.
- **Un nombre tapado en los datos de Atlas no es un dato que falte.** Siete
  personajes traen el Noble Fantasma como `???` porque en FGO es un secreto de
  la historia: se limpia al leerlo (`MARCAS_TAPADAS`, `noble_fantasma_desde`) y
  la ficha dice "Nombre desconocido". Ojo con `NobleFantasma.__bool__`, que
  mira `nombre or oculto`: si mirara solo el nombre, uno tapado pasaria por
  "no tiene", que es lo que significa `SIN_NOBLE_FANTASMA` y lo que llevan las
  Sombras.
- **Cancelar una guerra no es que la gane el último que quedaba.**
  `/terminar-guerra` la cierra sin ganador, y por eso `Guerra.cancelada` existe
  aparte de `Fase.TERMINADA`: `ganador()` cuenta los activos, así que sin ese
  campo cortar una guerra de dos en la que uno ya estaba eliminado coronaría al
  otro. `cancelada` no se guarda en la base de datos y no hace falta, porque la
  fase TERMINADA ya hace que no se vuelva a cargar. Y acuérdate de que
  `terminar_guerra()` tiene que borrar el combate de `self.combates`, que vive
  en el Cog y no en la guerra.
- **El simulador paga el oro de la batalla por su lado.** `_jugar_guerra` no
  pasa por `dia.anotar_batalla` (llama a `registrar_derrota` directamente), así
  que el oro de ganar una batalla está escrito **dos veces**: en `anotar_batalla`
  y en el simulador. Es la misma trampa que tuvo `caidos[0]` durante semanas. Si
  cambias cómo se paga, cámbialo en los dos sitios.
- **El balance de los objetos no se puede medir todavía**, porque ni la IA ni
  el simulador los usan: `VALOR_POR_EFECTO_DE_OBJETO` es un número razonado y
  no medido, y es la única constante de combate que no cumple la regla de
  medirla. Lo que sí se midió es que el inventario no movió la justicia de la
  guerra (cuatro semillas de 600: 14.2%, 15.0%, 14.5%, 11.2% contra el 14.3%),
  y eso solo dice que los bots no los usan. Antes de tocar esos valores hay que
  enseñar a `ai.py` a usar objetos y medir cuántos duelos gana quien lleva uno
  contra quien no. Está el primero en `puntos-abiertos.md`.
- **Una traduccion nueva del importador va en la tabla de segunda vuelta**
  (`EFECTOS_POR_BUFF_SECUNDARIOS`, `EFECTOS_POR_FUNCION_SECUNDARIOS`), no en la
  principal. `habilidad_de` se queda con la primera funcion que sabe traducir,
  asi que una entrada nueva en la tabla principal le cambia el efecto a
  habilidades que **ya tenian uno**: medido, 5 de critico y 1 de ataque se
  volvieron mana sin que nadie lo pidiera. La segunda vuelta solo se mira
  cuando ninguna funcion dio efecto, asi que rellena huecos y no toca nada mas.
- **Ninguna habilidad se queda sin efecto, y 39 lo tienen puesto a mano.**
  El importador sabe traducir 1005 de las 1044; las otras 39 se llenaron el
  2026-11-09 en `data/personajes.json` (34 con `bajar_mana`, 5 con `evasion`),
  porque una habilidad vacia **se le ofrecia al jugador en el menu de combate**
  y le gastaba el turno a cambio de nada, mientras la IA nunca la usaba
  (`ai._cuanto_paga` devuelve 0 para `NINGUNO`): una trampa que solo pisaban
  las personas. El precio es que en esas 39 el efecto **no sale de lo que la
  habilidad dice en la obra**, que es media regla de la casa; esta asumido y
  escrito en `puntos-abiertos.md`. Hay una prueba que falla si vuelve a
  aparecer un hueco, asi que una reimportacion que traiga personajes nuevos
  pide llenarlos igual.
- **No todo el que esta en `personajes.json` es una ficha escrita a mano.**
  Desde esas 39 hay 36 retoques que solo cambian el efecto de una habilidad y
  no traen rasgo ni Noble Fantasma propios, asi que una prueba que recorra ese
  archivo tiene que mirar **que** retoca cada ficha y no exigirle todo a todas
  (`test_los_retocados_a_mano_estan_completos`).
- **Un efecto negativo es un bono con el valor en negativo**, no una regla
  nueva: `BAJAR_ATAQUE` y `BAJAR_DEFENSA` entran como bonos de ataque y de
  defensa sobre **otro** combatiente (`BONO_DEL_NEGATIVO`), y las cuentas que
  ya existian los leen igual. Por eso hay `SUELO_BONO`: sin suelo, dos rivales
  turnandose dejan a alguien sin pegar nada. Y una bajada de defensa **ya
  llega al suelo ella sola**, asi que apilar otra no baja mas.
- **Un efecto negativo nunca se lo puede poner nadie a si mismo**, y lo
  sostienen dos sitios: `Objetivo.OTRO` en la ficha y un guardian en el
  importador (negativo y objetivo enemigo van juntos o no van). Si anades un
  efecto negativo, tiene que estar en `EFECTOS_NEGATIVOS` y **o bien** en
  `BONO_DEL_NEGATIVO` **o bien** en `EFECTOS_INSTANTANEOS`, y hay una prueba
  que lo exige.
- **Negativo e "`es un bono al reves`" no son lo mismo**, desde que existe
  `BAJAR_MANA`: ese es negativo (apunta al rival) pero instantaneo, igual que
  el `MANA` del que es espejo, asi que no esta en `BONO_DEL_NEGATIVO`. En
  `ai.py` hay que preguntar `hab.efecto in BONO_DEL_NEGATIVO` antes de ir a
  mirar el bono del rival; con `hab.negativa` es un `KeyError`.
- **`BAJAR_MANA` es la unica habilidad que puede valer 0 por quien hay
  enfrente** y no por quien la lleva: quitarle mana a quien tiene 0 no retrasa
  nada. Por eso `ai._cuanto_paga` recibe el blanco, y por eso la cuenta usa el
  costo del Noble Fantasma **del rival**.
- **Esquivar y aguantar se gastan de uno en uno** (`gastar_bono`), no por
  turnos: si duraran por turnos, una evasion de dos turnos esquivaria los tres
  ataques de una batalla de cuatro.
- **Para la IA, un debuff no es un regalo.** `_mejor_habilidad` sigue
  descartando lo que apunta a otro **si es un beneficio** (regalarselo a un
  rival es decision de Master), pero un negativo es un ataque y si lo usa, y
  lo apunta al mismo rival al que iba a pegar.
- **Una habilidad nueva no se mide contra no hacer nada: se mide contra las
  otras dos del personaje**, porque compiten por el mismo turno. El duelo
  espejo con una sola habilidad dice cosas que el plantel desmiente: con
  `bajar_defensa` a 0.60 la habilidad rendia un 70.5% y **Elisabeth Bathory
  ganaba el 100%** de sus duelos. La medida buena es *cada personaje que la
  lleva contra si mismo con esa habilidad muerta*, con cuatro semillas.
- **`BAJAR_ATAQUE` esta a 0.40 a sabiendas de que la IA lo juega regular**
  (41% contra el hueco vacio), porque a 0.50 la habilidad rinde bien pero el
  plantel se desparrama y alguien llega al 97%. Es el unico numero asi. El
  fondo es que la IA mide mal la mitigacion, lo mismo que hace que defenderse
  sea debil; ver `puntos-abiertos.md`.
- **Un objeto no puede tener los cuatro efectos nuevos** y eso es una
  decision: un objeto no cuesta el turno, asi que esquivar o debilitar gratis
  seria una habilidad gratis. `VALOR_POR_EFECTO_DE_OBJETO` no los tiene y una
  prueba lo exige.
- El código va sin acentos ni eñes (se escapan raro en algunas consolas de
  Windows); los documentos de `docs/` sí llevan acentos.
