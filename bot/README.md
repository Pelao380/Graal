# Graal: el bot

Codigo del bot. Las reglas del juego estan en `../docs/reglas-graal.md`.

## Como se organiza

```
bot/
├── requirements.txt     Dependencias
├── .env.example         Plantilla de credenciales (copiar a .env)
├── src/
│   ├── bot.py           Arranque del bot y conexion a Discord
│   ├── commands.py      Comandos de barra
│   ├── db.py            Esquema y conexion SQLite
│   ├── simulator.py     Simulador para balancear
│   └── game/            Logica pura del juego, sin Discord
│       ├── textos.py    Catalogo de frases en espanol e ingles
│       ├── personajes.py Fichas, rasgos y habilidades
│       ├── servant.py   Servants, niveles, XP, mana
│       ├── battle.py    Motor de batalla por turnos
│       ├── combate.py   La batalla que espera decisiones de la gente
│       ├── dia.py       Abrir y cerrar un dia de guerra
│       ├── npc.py       Combates de entrenamiento
│       ├── war.py       Lobby, dias, fases, formacion de batallas
│       └── ai.py        IA que reemplaza a un ausente
└── tests/               Pruebas de la logica
```

Lo importante de esta division: todo `src/game/` se puede probar y simular sin
token, sin internet y sin encender el bot. Solo `bot.py` y `commands.py`
dependen de Discord.

## Puesta en marcha

Desde esta carpeta (`bot/`), en PowerShell:

```powershell
# 1. Entorno aislado para no ensuciar el Python del sistema
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencias
pip install -r requirements.txt

# 3. Credenciales
copy .env.example .env
# abrir .env, pegar el token del bot y el ID del servidor de pruebas

# 4. Base de datos (crea bot/graal.db con las 9 tablas)
python -m src.db
python tools/ver_db.py          # para abrirla y ver que hay dentro

# 5. Comprobar el .env y que todo carga, sin conectarse a Discord
python tools/comprobar_bot.py

# 6. Arrancar
python -m src.bot
```

Si PowerShell no deja activar el entorno, hay que permitir scripts una vez:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### La aplicacion en Discord

1. En el Portal de Desarrolladores, **New Application**, y en la pestana
   **Bot**, *Reset Token* para copiar el token a `.env`. No hace falta
   activar ningun Intent privilegiado: con comandos de barra basta.
2. Invitarlo al servidor con los permisos minimos, en **OAuth2 > URL
   Generator**: scopes `bot` y `applications.commands`, y permisos *Send
   Messages* y *Use Slash Commands*.
3. Poner `GUILD_ID` en `.env` con el ID del servidor de pruebas (click derecho
   en el servidor, *Copiar ID*, con el Modo desarrollador activado). Asi los
   comandos aparecen al instante; sin eso Discord tarda hasta una hora.

### Que se puede probar hoy

Funciona de punta a punta: abrir la guerra en espanol o en ingles, llenarla
con bots, ver el estado y si el Grial esta en juego, la ficha del Servant con
sus habilidades y enfriamientos, y los combates NPC con su registro.

```
/crear-guerra preparacion:1 hora idioma:EN (english)
/unirse-a-guerra         (los demas; con 7 personas arranca sola)
/empezar-guerra          (llena los cupos con la IA y arranca el dia 1)
/estado-guerra
/invocar                 (llama a tu Servant; cuando quieras, el dia 1)
/empezar-batallas        (cierra la preparacion; solo quien abrio la guerra)
/estadisticas            (tu ficha y tu menu de botones, en privado)
/entrenar                (hasta 4 por dia)
```

Al empezar, el bot menciona a los jugadores y deja un boton "Abrir mi menu":
cada uno abre el suyo en privado, con botones para invocar, sus estadisticas,
entrenar, planear el ataque del dia y ver el estado de la guerra. **Ese boton
vuelve al canal cada dia**, porque el dia nuevo trae entrenamientos otra vez,
un ataque que planear y un "ya acabe mi dia" que volver a decir. Cuando se
cierra la preparacion el boton que aparece es otro, "Abrir mi combate", y es
donde se pelea.

**El ataque se planea desde el menu.** "Planear ataque" abre un desplegable
con los Masters que siguen en pie; de quien no hayas peleado solo ves su
nombre y sus derrotas, asi que la primera vez eliges a ciegas. A quien atacas
no lo sabe nadie mas: el unico sitio donde se ve es tu propio boton, que pasa
a decir "Atacas a X". Se puede cambiar hasta que se cierre el dia, pero no
despues de decir que acabaste.

**La guerra no reparte los Servants al arrancar.** El sorteo esta hecho, pero
cada Master llama al suyo cuando quiera a lo largo del dia 1, con `/invocar` o
con el boton. Al cerrarse el dia se invoca solo por quien no lo haya pedido:
nadie pelea sin Servant. Hasta entonces no se puede entrenar ni atacar, pero
si te pueden atacar.

**El dia no espera necesariamente el plazo.** Quien abrio la guerra cierra la
preparacion cuando quiera con `/empezar-batallas` o con el boton rojo de su
menu: se invoca por quien falte y se forman las batallas. Asi una guerra entre
amigos o contra bots se juega de punta a punta sin esperar horas.

**Y entonces se pelea.** El canal deja un boton "Abrir mi combate" y cada
quien pelea su batalla en privado, turno a turno: atacar, defenderse, usar una
habilidad o liberar el Noble Fantasma. **Las decisiones de un turno son
simultaneas y secretas**: nadie ve lo que eligio otro y el turno no se resuelve
hasta que han elegido todos. Si cae alguien y quedan dos o mas en pie se vota
si la batalla sigue. Quien no conteste en 5 minutos tiene su turno decidido
por la IA, que es lo que evita que una persona ausente deje la guerra parada.
El dia siguiente empieza cuando se acaba la ultima batalla.

Y si nadie lo cierra, **se cierra solo cuando se agota la ventana** de
preparacion (30 minutos, 1 hora o 24 horas, lo que se eligio al crear la
guerra). De eso se encarga el vigilante de `src/vigilante.py`, que mira el
reloj cada 30 segundos. El plazo no espera a nadie: para eso existe.
`/estado-guerra` dice lo que queda.

**Un reinicio ya no pierde la guerra.** Se guarda en `graal.db` despues de cada
accion (`src/repositorio.py`) y se lee al arrancar, con su plazo incluido: si
la ventana vencio mientras el bot estaba apagado, el dia se cierra en la
primera revision al volver. Para mirar lo guardado, `python tools/ver_db.py`.

Eso si, el cierre del creador **solo cuando todos han acabado su dia**: cada quien lo dice con el
boton "Ya acabe mi dia", y despues ya no puede entrenar. Si no, el creador
entrenaria y cerraria antes de que los demas entrenen, que medido le doblaba
las victorias. Los bots estan listos desde que se abre el dia, asi que en una
guerra contra bots nunca hacen esperar. Las batallas entre bots las sigue
resolviendo la IA, porque no hay a quien esperar.

**Nadie sabe que Servant lleva nadie hasta que pelea con el.** El canal solo
anuncia que alguien ha invocado; la ficha de otro Master aparece en tu estado
cuando le has peleado, y ya no se borra. De ahi dos cosas que se ven raras si
no se sabe por que: `/estado-guerra` es privado, porque no es el mismo para dos
personas, y **el detalle de una batalla ya no se publica** (lo lee cada
participante desde su menu, con "Ver mi ultima batalla"), porque las frases
nombran las habilidades y eso delata al Servant. El canal se queda con quien
peleo contra quien y quien cayo: menos espectaculo a cambio de que declarar un
ataque sea una apuesta.

Esos son los nombres en espanol. El idioma por defecto es el ingles, asi que
quien no tenga Discord en espanol vera `/create-war`, `/join-war`,
`/start-war`, `/war-status`, `/summon`, `/start-battles`, `/stats` y `/train`. El nombre lo decide el
idioma del cliente de cada uno; lo que el bot responde va siempre en el idioma
de la guerra.

Lo que **todavia no** esta en Discord: el maximo del dia (una batalla puede estirarse turno a
turno todo lo que la gente quiera, y lo unico que la corta es el tope de 60
turnos) y guardar una batalla a medias, que un reinicio del bot pierde: el
vigilante acaba el dia con la IA y la guerra sigue. Ver
`docs/puntos-abiertos.md`.

## Probar sin token

Las pruebas y el simulador no necesitan Discord ni el token:

```powershell
python -m unittest discover -s tests -t .

python -m src.simulator --semilla 7 niveles
python -m src.simulator --semilla 7 triangulo
python -m src.simulator --semilla 7 plantel
python -m src.simulator --semilla 7 npc --dia 1
python -m src.simulator --semilla 7 duelo --a Heracles --b Medea
python -m src.simulator --semilla 7 habilidades
python -m src.simulator --semilla 7 guerras
```

El modo `guerras` juega guerras enteras con la IA en todos los lados y es la
unica prueba de punta a punta del ciclo del dia: entrenar, declarar ataques,
formar batallas y eliminar. Tambien dice si jugar contra bots es justo.

El modo `habilidades` enfrenta a cada personaje contra si mismo sin
habilidades, que es la forma de ver si lo que dan paga el turno que cuestan.
Con `--escala` se multiplican todos los efectos y con `--efecto ataque` se
mide una familia sola.

## El token

Va en `.env`, que `.gitignore` excluye. Nunca en el codigo ni en el
repositorio. Si alguna vez se filtra, se regenera en el Portal de
Desarrolladores y el viejo deja de servir.

## El plantel

Los 349 personajes salen del export de Atlas Academy. Para regenerarlo cuando
el juego cambie:

```powershell
cd data
curl.exe -L -C - -o nice_servant.json "https://api.atlasacademy.io/export/NA/nice_servant.json"
cd ..
python tools/importar_servants.py
```

El importador prefiere `nice_servant.json`, que trae los nombres de las
habilidades y de los Nobles Fantasmas **y sus efectos**, y cae en
`basic_servant.json` si no está, que solo da estadisticas. Si la descarga se corta, el JSON queda sin cerrar y el importador lo
dice en vez de fallar de forma rara: un export completo termina en `]`.

Eso reescribe `data/personajes_generados.json` y no toca `data/personajes.json`,
donde viven los rasgos y nombres escritos a mano.

## Los textos

Todo lo que lee el jugador esta en `data/textos.json`, en espanol y en ingles,
y se pide por clave:

```python
from .game.textos import t
t("batalla.cae", "en", nombre="Emiya")   # "Emiya falls."
```

Se valida al cargar: si a una clave le falta un idioma, o los huecos entre
llaves no coinciden entre idiomas, revienta al arrancar en vez de ensenar la
clave cruda en Discord. Para anadir un idioma se pone su codigo en `_idiomas`
y una linea mas por frase; el codigo no cambia.

## Estado

Hecho:

- Motor de batalla por turnos completo: decisiones ocultas, orden por
  velocidad, mana, defensa con la regla de la segunda defensa seguida, Noble
  Fantasma, ataques que no conectan, votacion y turno especial.
- Combates NPC con dificultad creciente y endurecimiento por dia, con tope
  para que una Sombra nunca sea un espejo mas fuerte que el jugador. Los
  cuatro se pueden ganar siempre (del 97% al 75% el dia 1, del 91% al 68% el
  dia 7) y ninguno es gratis.
- Niveles y curva de XP (20 + 5n).
- Ciclo de la guerra: lobby de 7, declaracion de ataques, formacion de
  batallas con tope de 4, eliminacion a las 2 derrotas.
- Cupos que llena la IA (`/empezar-guerra`), para jugar solo contra 6 bots. El
  Grial solo se entrega con 4 personas de verdad o mas.
- IA que reemplaza a un ausente.
- Habilidades con efecto: cinco efectos propios traducidos de FGO, objetivo a
  elegir cuando se puede dar a otro, enfriamiento por efecto y valores medidos
  con el simulador.
- Espanol e ingles: todas las frases en `data/textos.json`, el idioma se elige
  al crear la guerra y la batalla se narra en ese idioma.
- Las guerras se guardan en `graal.db` entre accion y accion, con los plazos en
  tabla para sobrevivir reinicios.
- El menu de combate: las batallas se juegan turno a turno desde Discord, con
  decisiones secretas y simultaneas, habilidades, Noble Fantasma y votacion.
- 330 pruebas y un simulador.

Pendiente:

- Guardar una batalla a medias: las tablas estan en el esquema, pero hoy un
  combate en curso vive en memoria y un reinicio lo pierde (el vigilante acaba
  el dia con la IA).
- Del vigilante de plazos falta el **maximo del dia**; la ventana de
  preparacion y los 5 minutos por turno ya estan.
- Los 160 efectos de habilidad que no se tradujeron (esquivar, aguantar un
  golpe mortal, debilitar al rival), y el plantel de nivel 15, que las
  habilidades ensanchan bastante (ver `../docs/puntos-abiertos.md`).
- Del idioma, lo que falta: los nombres de los comandos de barra, que siguen
  solo en espanol, y decidir si lo privado va en el idioma de cada jugador.
- Los Nobles Fantasmas tienen nombre pero todos hacen lo mismo (x3 de dano), y
  falta el catalogo de objetos.
