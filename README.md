# Graal

Bot de Discord para jugar **guerras del santo grial** al estilo de *Fate*: siete
Masters invocan un Servant cada uno y pelean por turnos, con decisiones ocultas
y simultáneas, hasta que queda uno solo. Los cupos que no llene nadie los llena
la IA, así que se puede jugar en solitario contra seis bots.

Python con discord.py y SQLite. **628 pruebas que corren sin token, sin red y
sin encender el bot**, y un simulador con el que están calibrados todos los
números del combate.

> Proyecto de fans, sin ánimo de lucro y sin arte oficial. No está afiliado a
> Type-Moon ni a Aniplex. Ver [LICENSE](LICENSE).

## Qué tiene de interesante

**El balance está medido, no estimado.** Ninguna constante del combate se toca
sin correr el simulador antes y después, y cada una lleva en el comentario qué
se midió y qué salió. Un ejemplo real, el de `BAJAR_ATAQUE`:

```
bajar_ataque 0.40 -> la habilidad rinde el 41% (peor que dejar el hueco vacío)
bajar_ataque 0.50 -> rinde el 66%
bajar_ataque 0.55 -> rinde el 93%, y la IA la prefiere a subirse el ataque

pero, contra el plantel completo de 348 personajes:
bajar_ataque 0.40 -> desviación 17.6%, máximo 91.7%
bajar_ataque 0.50 -> desviación 18.3%, máximo 97.2%
```

Se quedó en **0.40**, el valor con el que la habilidad rinde *peor*, porque el
otro desparrama el plantel y corona a un personaje al 97%. Las dos medidas se
contradecían y hay una regla de la casa que desempata: vale la del plantel, no
la del duelo. Lo que queda por arreglar no es ese número, es que la IA mide mal
la mitigación — y eso también está escrito, en `docs/puntos-abiertos.md`.

**La lógica del juego no sabe nada de Discord.** Todo `bot/src/game/` se puede
probar y simular sin tocar la red; solo dos archivos importan `discord`. Eso es
lo que hace posible el simulador, y el simulador es lo que hace posible medir.

**Los personajes viven en datos, no en código.** Los 348 Servants se derivan del
export público de Atlas Academy, y de ahí sale **qué** hace cada una de sus 1044
habilidades; **cuánto** da lo decide el juego, con una lista cerrada de diez
efectos. Así un personaje nuevo no puede inventar una regla que rompa el
combate. El presupuesto de estadísticas se valida al cargar: si una ficha no
cuadra, no entra.

**Ninguna frase que lea el jugador está en el código.** Viven en un archivo de
textos, en español y en inglés, y se valida al arrancar que a ninguna clave le
falte un idioma ni le cuadren mal los huecos. El idioma de la guerra lo elige
quien la crea; el nombre de los comandos lo decide el Discord de cada uno.

**El secreto es una regla, no un detalle.** No sabes qué Servant lleva nadie
hasta que peleas contra él, así que nada de lo que sale al canal puede nombrar
un Servant ni una habilidad: el detalle de una batalla lo lee cada participante
en privado, desde su menú.

## Cómo se juega

Un día de guerra tiene dos mitades: la preparación (entrenar contra NPC,
declarar a quién atacas, usar objetos) y las batallas, en grupos de 2 a 4. Dos
derrotas y estás fuera. Dentro de la batalla eliges atacar, defender, una
habilidad o el Noble Fantasma, que cuesta 100 de maná y multiplica el daño por
tres.

Las reglas completas están en [`docs/reglas-graal.md`](docs/reglas-graal.md). Si
no has visto *Fate* en tu vida, empieza por
[`docs/como-jugar.md`](docs/como-jugar.md), que es media página.

## Probarlo sin token

```bash
cd bot
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m unittest discover -s tests -t .   # 628 pruebas
```

Y el simulador, que es la parte divertida:

```bash
python -m src.simulator --semilla 7 plantel      # busca personajes rotos
python -m src.simulator --semilla 7 triangulo    # matriz de emparejamientos
python -m src.simulator --semilla 7 guerras -n 600   # guerras enteras
python -m src.simulator --semilla 7 economia     # cuánto oro da una guerra
```

Para encenderlo de verdad hace falta un token de Discord en `bot/.env` (hay una
plantilla en `bot/.env.example`). El token nunca va al repositorio.

## Estructura

```
Graal/
├── docs/
│   ├── como-jugar.md       Lo esencial, para quien no conoce Fate
│   ├── reglas-graal.md     Las reglas completas: la especificación
│   ├── decisiones.md       Qué se decidió y por qué, con las medidas
│   └── puntos-abiertos.md  Lo que falta, por orden
└── bot/
    ├── src/game/           El juego: combate, guerra, día, IA, personajes
    ├── src/                La capa de Discord: bot, comandos, repositorio
    ├── data/               Personajes, objetos y textos (es/en)
    ├── tests/              628 pruebas
    └── tools/              Importar el plantel, revisar la base de datos
```

`docs/decisiones.md` es el registro de decisiones del proyecto, con el motivo y
la medida de cada una. Es el documento que explica por qué el código es como es.

## Estado

Jugable de principio a fin: lobby, invocación, entrenamiento contra NPC,
niveles y habilidades, batallas por turnos con menús privados, plazos que
sobreviven a un reinicio, tienda con dos monedas, inventario, Sellos de Comando
y rendirse. Se juega en español o en inglés.

Lo que falta, con detalle en [`docs/puntos-abiertos.md`](docs/puntos-abiertos.md):

- **Enseñar a la IA a usar objetos y Sellos.** Es lo primero, porque hasta que
  no lo haga hay dos constantes del combate que no se pueden medir, y la regla
  de la casa dice que no se toca un número sin medirlo.
- **La mecánica del catalizador**: qué pasa exactamente al usar uno al invocar.
- **El máximo del día**, para que una batalla no se estire sin límite.
- Guardar una batalla a medias: hoy vive en memoria y un reinicio la pierde (la
  guerra no, que sigue; el vigilante cierra el día con la IA).
