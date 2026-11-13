# Graal: cómo se juega

Para quien no ha visto *Fate* nunca. Solo lo esencial; las reglas completas
están en `reglas-graal.md`.

## La idea en cuatro frases

Siete personas invocan cada una a un héroe del pasado (un **Servant**) y pelean
entre ellas hasta que queda una sola. Tú eres el **Master**: no peleas tú, pelea
tu Servant, y tú decides qué hace. El que queda en pie gana el Grial.

No hace falta saber nada de *Fate*: el Servant que te toca es un personaje con
tres números y tres habilidades, y lo demás son estas reglas.

## Antes de empezar

Alguien crea la guerra, los demás se unen y el creador la arranca. Si no se
juntan siete, los huecos los rellenan **bots**, que juegan igual que una persona.

Al arrancar, cada Master pide su Servant: **te toca al azar** y no puedes
elegirlo. Lo ves solo tú, con su clase, sus números y sus habilidades.

**Nadie sabe qué Servant lleva nadie.** El de otro lo descubres **peleando
contra él**, y una vez visto ya no se olvida. Lo que sí es público de todos es su
nombre, cuántas derrotas llevan y cuántos Sellos de Comando les quedan.

## Un día de guerra

La guerra va por **días**, y cada día tiene dos mitades.

**1. Preparación.** Cada uno, por su cuenta y en privado:

- **Entrenar**: pelear contra Sombras (enemigos de práctica, 4 intentos al día).
  Ganar da experiencia, oro y a veces un objeto. Perder contra una Sombra no te
  elimina, pero llegas a la batalla con menos vida ese día.
- **Declarar a quién atacas**: eliges a otro Master. A ciegas la primera vez,
  porque no sabes qué Servant lleva.
- **Decir que estás listo** cuando ya hiciste todo lo que querías.

Cuando todos dicen que están listos (o se agota el plazo) se cierra la
preparación. **Ojo: decir "listo" cierra tu día**, y después ya no puedes
entrenar ni cambiar de objetivo.

**2. Las batallas.** Con las declaraciones de todos se forman grupos de **2 a 4
Servants**. Si nadie te declaró y tú no declaraste a nadie, ese día descansas.

## Dentro de una batalla

Se juega por turnos. En cada turno, todos eligen **a la vez y en secreto**, y
hasta que no ha elegido el último no pasa nada. Tienes cuatro cosas que hacer:

| Acción | Qué hace | Maná |
| --- | --- | --- |
| **Atacar** | Daño a un rival que tú eliges | +15 |
| **Defender** | Recibes la mitad del daño este turno | +20 |
| **Habilidad** | Una de tus tres; gasta el turno entero y luego se enfría unos turnos | +10 |
| **Noble Fantasma** | El ataque definitivo: **×3 de daño** | −100 |

El **maná** empieza en 20 y sube con cada acción. Al llegar a 100 puedes lanzar
tu **Noble Fantasma**, y no hay límite: cada vez que vuelvas a juntar 100,
otro. Llegar a 100 cuesta unos 6 turnos, así que en una batalla normal sale uno
o dos. Decidir si gastas el turno en una habilidad, sabiendo que eso retrasa tu
Noble Fantasma, es la decisión que importa.

Hay más cosas que no tienes que calcular: el daño varía un poco al azar, un 15%
de los golpes son **críticos** (×1.8) y un Servant más rápido que el que le pega
puede esquivar solo por eso.

La batalla **acaba cuando cae el primero**. Si quedan dos o más en pie, se
pregunta si seguir o parar ahí.

Si no eliges nada en 5 minutos, la IA elige por ti: nadie se queda esperando.

## Las clases y quién le gana a quién

Hay 8 clases. La clase **no** da estadísticas (esas son del personaje); decide
dos cosas: qué hueco ocupa en la invocación y la ventaja del triángulo.

| Clase | Pega más contra | Recibe más de |
| --- | --- | --- |
| **Saber** | Lancer | Archer |
| **Lancer** | Archer | Saber |
| **Archer** | Saber | Lancer |
| **Rider** | — | — |
| **Caster** | — | — |
| **Assassin** | — | — |
| **Berserker** | — | — |
| **Ruler** | — | — |

El triángulo es solo entre esas tres:

```
   Saber  →  Lancer
     ↑          ↓
   Archer  ←————┘
```

Se lee así: **Saber le gana a Lancer, Lancer le gana a Archer y Archer le gana a
Saber.** Las otras cinco clases son neutrales: ni ventaja ni desventaja contra
nadie.

Tener ventaja es **+10% de daño al pegar y −10% al recibir**. Pesa, pero no
decide el combate: está medido, y a ±20% la clase ganaba sola el 96% de las
peleas, que es demasiado.

De las 8 clases, en una guerra entran **7**. El Ruler es raro (5% de las
guerras) y cuando sale ocupa el hueco de otra, que ese día no aparece.

## Quedar fuera, y ganar

- **Dos derrotas contra otro Master y estás fuera.** Las Sombras del
  entrenamiento no cuentan para esto.
- También puedes **rendirte** desde tu menú (hay que pulsar el botón dos veces,
  y no se deshace).
- Gana quien quede solo en pie.

## Lo que se acumula

- **Experiencia**: tu Servant sube de nivel hasta el 15, y en los niveles 5, 10
  y 15 desbloquea sus tres habilidades.
- **Oro**: lo da entrenar y ganar batallas, compra objetos en la tienda y
  **muere con la guerra**.
- **Objetos**: cosas de un uso. Uno de ellos se puede usar **dentro** de una
  batalla y no gasta tu turno, pero solo uno por batalla.
- **Sellos de Comando**: tres para toda la guerra. Dentro de una batalla, y sin
  gastar tu turno, uno de ellos te llena el maná (Noble Fantasma ya), te cura o
  te deja repetir una habilidad. Uno por batalla, y gastado no vuelve.
- **Griales**: la recompensa de ganar una guerra. Esos **sí** se quedan en tu
  cuenta de una guerra a otra.

## Los comandos

Casi todo se hace con botones, en mensajes que solo ves tú. Los comandos son
pocos:

| Comando | Para qué |
| --- | --- |
| `/crear-guerra` | Abrir una guerra en este canal |
| `/unirse-a-guerra` | Entrar en ella |
| `/empezar-guerra` | Arrancarla (solo quien la creó) |
| `/invocar` | Pedir tu Servant |
| `/estado-guerra` | Cómo va todo, en privado |
| `/estadisticas` | La ficha de tu Servant |
| `/entrenar` | Pelear contra una Sombra |
| `/empezar-batallas` | Cerrar la preparación del día |
| `/mi-cuenta` | Tus griales y tus guerras ganadas |
| `/terminar-guerra` | Cancelarla (solo quien la creó) |

Si tienes Discord en inglés verás los mismos comandos en inglés (`/create-war`,
`/summon`, `/train`…). Lo que el bot **responde** va en el idioma que eligió
quien creó la guerra.
