# BeSoccer Pro — detección de talento por demarcación

Motor para cruzar datos de jugadores de **varias ligas y países** a partir de
los exports de BeSoccer Pro / Visother Pro, y sacar dos tipos de lista:

1. **Los mejores hoy** en cada demarcación, comparables entre ligas distintas.
2. **Los que rinden poco hoy pero tienen techo alto** — el perfil que interesa
   fichar antes de que suba de precio.

Todo el cálculo es local sobre tus propios exports. No incluye ni requiere
datos de terceros.

---

## Cómo meter tus datos (empieza por aquí)

Tu cuenta de BeSoccer Pro es la que tiene el acceso, y así se queda. Lo que
hace falta es un puente entre la plataforma y este motor. Dos caminos:

### Camino A — Exports CSV (funciona hoy, sin depender de nadie)

BeSoccer Pro exporta en PDF y **CSV**. Ese CSV es todo lo que hace falta:

1. En la plataforma, monta la búsqueda avanzada con tus filtros (liga,
   temporada, edad, minutos, demarcación).
2. Expórtala a CSV. Guarda la búsqueda para repetirla cada mes.
3. Deja los ficheros en `data/` y lanza los comandos de abajo.

Un fichero por liga. Da igual que las cabeceras estén en castellano o inglés,
que el separador sea `;` o `,`, o que falten columnas: el cargador lo resuelve
y `doctor` te avisa de lo que no reconozca.

**Cuantas más columnas metas en el export, mejor.** Prioriza: minutos,
demarcación, edad, xG, xA, y —si tu plan las incluye— valor de mercado,
estimación salarial y fin de contrato. Esas tres últimas alimentan el
"escaparate" y el filtro de vencimiento, que es donde está el margen de
negociación.

### Camino B — API de BeSoccer (para automatizarlo)

Ojo con esto: **la API de BeSoccer (`api.besoccer.com`) es un producto aparte
de BeSoccer Pro**, con sus propios planes y su propia clave. Que pagues la
licencia Pro no implica que tengas API.

Habla con tu gestor de cuenta y pregunta dos cosas concretas: si tu contrato
incluye acceso a la API, y si no, qué cuesta añadirlo. Pide una **clave de
API de servicio**, no des tus credenciales personales.

```bash
export BESOCCER_API_BASE="https://…"     # lo confirma el proveedor
export BESOCCER_API_TOKEN="…"            # clave, nunca en un fichero del repo
python -c "from besoccer_pro import api; print(len(api.fetch('players')))"
```

El cliente (`besoccer_pro/api.py`) es genérico: URL base, estilo de
autenticación, ruta al array de registros y parámetros de paginación, todo
configurable. Cuando tengas la documentación real, se ajusta la config y queda
automatizado.

> El token va **solo** en variables de entorno. `config/api.yaml` está en el
> `.gitignore` para que nadie lo suba por error.

### Lo que no vamos a hacer

Automatizar un navegador contra `pro.besoccer.com` con tu sesión iniciada para
raspar la web. Es frágil, y casi con seguridad va contra las condiciones de tu
licencia — precisamente el tipo de cosa que puede costarte la cuenta. El export
CSV consigue lo mismo de forma legítima.

---

## Uso

```bash
pip install -r requirements.txt

# 0) Datos de prueba sintéticos, para ver el sistema funcionando ya
python tools/make_sample.py

# 1) ¿Se entienden mis columnas? Primer comando con un export nuevo.
python -m besoccer_pro doctor --input data/sample/

# 2) Qué hay en el pool cargado
python -m besoccer_pro summary --input data/sample/

# 3) Los mejores delanteros, cruzando todas las ligas cargadas
python -m besoccer_pro rank --input data/sample/ --position ST --top 30

# 4) LA LISTA: techo alto, poco reconocimiento hoy
python -m besoccer_pro breakouts --input data/sample/ --max-age 22 --top 40

# 5) Rinden por 90 más de lo que dice su rol (suplentes de nivel)
python -m besoccer_pro underperformers --input data/sample/ --position CM

# 6) Ficha individual con percentiles frente a sus pares
python -m besoccer_pro profile --input data/sample/ --player "Apellido"

# 7) Talento con el contrato acabándose: techo alto y poca fuerza negociadora
python -m besoccer_pro breakouts --input data/ --max-age 23 --max-contract-years 1

# Cualquier listado se exporta con -o
python -m besoccer_pro breakouts --input data/ --max-age 21 -o informes/sub21.xlsx
```

Demarcaciones: `GK` portero, `CB` central, `FB` lateral, `DM` pivote,
`CM` mediocentro, `AM` mediapunta, `W` extremo, `ST` delantero.

Si una columna no se reconoce, `doctor` te la lista y la mapeas sin tocar código:

```bash
python -m besoccer_pro rank --input data/ --map "Índice XYZ=xg" "Mins=minutes"
```

---

## Receta: 1ª y 2ª RFEF

Categorías territoriales, y eso cambia dos cosas.

**1. Exporta SIEMPRE la columna `Grupo`.** 2ª RFEF tiene cinco grupos y 1ª RFEF
dos, y el nivel entre ellos no es el mismo. Sin esa columna el motor mete a los
cinco grupos en la misma coctelera y el percentil —que es la base de todo—
queda falseado. Con ella, cada jugador se compara **dentro de su grupo**.
Compruébalo: la columna `pool_type` debe decir `liga+grupo+posicion`.

**2. Baja el umbral de techo.** El defecto (`--min-potential 60`) está pensado
para ligas top. Con coeficiente 0,62 y 0,52, en RFEF deja fuera a casi toda la
categoría. Medido sobre un pool de 756 jugadores: con 60 salen 2 candidatos,
con 40 salen 8 y la lista es trabajable.

```bash
# 1ª RFEF: el escalón alto, más candidatos a dar el salto ya
python -m besoccer_pro breakouts --input data/rfef.csv \
    --league "Primera Federación" --max-age 23 --min-minutes 700 \
    --min-potential 45 --top 40 -o informes/1rfef.xlsx

# 2ª RFEF: apuesta más larga, hay que bajar más el umbral
python -m besoccer_pro breakouts --input data/rfef.csv \
    --league "Segunda Federación" --max-age 22 --min-minutes 700 \
    --min-potential 38 --top 40 -o informes/2rfef.xlsx

# Filiales aparte: un chaval del Villarreal B no es la misma operación
# que uno de un club modesto (ficha, cláusula e interlocutor distintos)
python -m besoccer_pro breakouts --input data/rfef.csv --reserves exclude \
    --max-age 23 --min-potential 40
```

**Los `Nivel` van a parecer bajos** (30-45 donde en LaLiga verías 70). Es
correcto: la escala es absoluta y cruza países. Un 42 en 2ª RFEF es un
jugador dominante *en 2ª RFEF*. Lo que ordena la lista es `Irrupcion`, no
`Nivel`.

**Cuidado con los minutos.** En estas categorías hay mucha rotación. Con menos
de 700 minutos la `Fiab.` baja de 0,45 y el dato es débil — úsalo para decidir
a quién ir a ver, no para decidir un fichaje.

---

## Destacar en un equipo flojo

Un jugador de zona baja está penalizado por el contexto: recibe peores pases,
ataca menos y defiende más. El percentil de liga no lo corrige. `standout_index`
(`Destaca`) sí: compara a cada jugador con **la media de sus propios
compañeros**, dejando fuera al jugador mismo del cálculo —incluirse diluye
justo la señal que se busca, y más cuanto más corta sea la plantilla.

```bash
# El brief clásico de agencia en un comando:
# sub-22, contrato acabándose, tirando del carro en su equipo
python -m besoccer_pro breakouts --input data/rfef.xlsx \
    --max-age 22 --min-minutes 700 --min-potential 40 \
    --min-standout 8 --max-contract-years 1 --top 40
```

`Destaca` alto en un equipo de mitad de tabla es señal fuerte. `Destaca` alto
en un equipo puntero suele ser solo un buen jugador en un buen equipo.

---

## Proyectar a una categoría concreta

`breakouts` te dice quién está infravalorado. `project` responde a otra
pregunta distinta y más útil para fichar: **¿quién puede jugar en Segunda?**

```bash
python -m besoccer_pro project --input data/rfef.xlsx \
    --target-league "Segunda División" --target-percentile 65 \
    --max-age 25 --top 30 -o informes/proyectan_a_segunda.xlsx
```

El listón sale de la propia escala del modelo:

```
listón = percentil_objetivo × coeficiente(liga_objetivo)
```

Con Segunda (0,77): **p50 = 38,5** (jugador de rotación), **p65 = 50,1**
(titular solvente), **p85 = 65,5** (top de la categoría). Elegir el percentil
es elegir para qué rol fichas.

Columnas: `Liston` el umbral, `Margen` cuánto lo supera, `YaLoEs` si **ya**
está a ese nivel hoy (fichaje inmediato) o solo proyecta (apuesta).
`--only-projects` deja únicamente a los segundos, que es donde está el precio.

### Calibración: léelo antes de usarlo

Medido sobre un pool de RFEF de 394 sub-25: **el listón p50 lo supera el 61%**.
Un filtro que aprueba a seis de cada diez no es un criterio. Con p65 baja al
19%, que ya es una lista trabajable.

El comando te imprime ese porcentaje en cada ejecución y te avisa si pasa del
35%. **Usa la lista como orden, no como aprobado**: quédate con los primeros
por `Margen` y olvídate del valor absoluto.

Por qué: el techo es una proyección **sin calibrar contra resultados reales**.
No hay en los datos ningún jugador del que sepamos si llegó o no, así que el
número ordena candidatos pero **no es una probabilidad**. Para convertirlo en
una de verdad hace falta el bucle de validación: exportar RFEF de una
temporada pasada, mirar quién está hoy en Segunda, y ajustar la curva de edad
con esos aciertos y fallos. Con dos temporadas de export se puede construir.

### El efecto de la edad, que sorprende

Con `--max-age 25` la lista sale copada por chavales de 17-20 años. No es un
fallo: a los 25 el margen de mejora es 0,26 y a los 18 es 0,94, así que un
sub-20 con los mismos números proyecta mucho más alto.

Consecuencia práctica: **filtrar hasta 25 años mezcla dos operaciones
distintas**. Un jugador de 24-25 en esa lista es un fichaje "listo ya" —mira
`YaLoEs`—; uno de 19 es un proyecto a dos años. Si buscas rendimiento
inmediato, usa `--min-age 22`. Si buscas plusvalía, `--max-age 21`.

---

## Cómo funciona el modelo

Cinco pasos, todos auditables en `besoccer_pro/scoring.py`:

**1. Se compara dentro de la liga, no en crudo.**
Un jugador se mide primero contra los de su misma demarcación **en su propia
liga** (percentil intra-liga). Los pesos por posición están en
`positions.py`: un central puntúa por duelos, aéreos e intercepciones; un
extremo por regate, xG y xA. Nunca se mezclan.

**2. Se traduce a escala común.**
Ese percentil se multiplica por el **coeficiente de liga** de
`config/leagues.yaml`. Un percentil 80 en Eredivisie (0,84) no vale lo mismo
que un 80 en Premier (1,00). Resultado: **Nivel actual**.

**3. Se castiga la muestra corta.**
Un 0,9 goles/90 en 300 minutos no es un dato, es ruido. Se aplica contracción
hacia la media según minutos jugados (`Fiab.` en las tablas: 900 minutos =
0,5). Sin esto, cualquier lista de talento se llena de chavales con cuatro
partidos.

**4. Techo = recorrido por edad × calidad demostrada.**

```
Techo = Nivel + margen_por_edad(edad) × (100 − Nivel) × (Calidad_por_90 / 100)
```

El margen de edad va de 1,0 a los 16 años hasta 0 a partir de los 30. Un
jugador de 30 años tiene techo igual a su nivel actual: ya es lo que es.

**5. Índice de irrupción = Techo − Escaparate.**
El "escaparate" es lo que hoy ve el mercado: minutos, nivel de liga y valor de
mercado si está en el export. **Techo alto + escaparate bajo = el jugador que
buscas.** Es la columna que ordena el comando `breakouts`.

### Las columnas de los listados

| Columna | Qué es |
|---|---|
| `Nivel` | Nivel actual creíble, ya contraído por minutos y traducido entre ligas |
| `Calidad/90` | Rendimiento por 90 minutos en bruto, sin castigo de muestra |
| `Techo` | Nivel proyectado si completa su desarrollo |
| `Escaparate` | Reconocimiento actual: minutos, liga, valor |
| `Irrupcion` | `Techo − Escaparate`. Alto = infravalorado |
| `Brecha` | `Calidad/90 − Nivel`. Alto = rinde más de lo que sus minutos reflejan |
| `Fiab.` | Fiabilidad de la muestra, 0-1 |
| `IdxBeSoccer` | El índice de rendimiento de la plataforma, si viene en el export |
| `AnosContr` | Años de contrato restantes |

### Los índices propios de BeSoccer

Si tu export trae el **índice de rendimiento, Elo, REAP o el rating de
potencial**, el motor los reconoce y los arrastra hasta los informes — pero
**no los mete en el cálculo**. Es deliberado: son composites construidos sobre
las mismas métricas, así que incluirlos sería razonar en círculo. El valor está
en tener dos criterios independientes uno al lado del otro. Cuando el `Techo`
y el `IdxBeSoccer` discrepan mucho en un jugador, ahí es donde merece la pena
poner el vídeo.

El **salario y el valor de mercado** sí entran, pero solo en el "escaparate":
son lo que el mercado ya paga, no una medida de rendimiento.

---

## Lo que hay que saber antes de fiarse de una lista

- **Los coeficientes de liga son criterio, no dato oficial.** Están puestos a
  ojo siguiendo ranking UEFA y valor de plantilla. Son el único parámetro
  subjetivo del modelo y **cambian los resultados**. Revísalos con tu criterio
  de scouting: `config/leagues.yaml`, y `python -m besoccer_pro leagues` para
  verlos. Una liga que no esté listada usa el valor por defecto (0,70) y te
  avisa por pantalla.
- **La calidad de la salida es la de tu export.** Sin `xG`/`xA` el modelo tira
  de goles y asistencias, que son más ruidosos. `doctor` te dice qué métricas
  faltan; los pesos se reponderan solos, pero con menos resolución.
- **Esto ordena la pila, no ficha.** Sirve para que el ojo humano mire a 30
  jugadores en vez de a 3.000. El vídeo y el informe de campo siguen mandando.
- **Porteros aparte.** Con las métricas de un export estándar, el modelo de
  portero es el más pobre de los ocho. Trátalo con más escepticismo.
- **Contexto táctico no medido.** Un pivote en un equipo que domina el balón
  acumula pases progresivos que otro no tiene ocasión de dar. El coeficiente de
  liga corrige país, no estilo de equipo.

---

## Estructura

```
besoccer_pro/
  columns.py    mapeo de cabeceras ES/EN -> nombres canónicos
  positions.py  demarcaciones y pesos de métricas por posición
  metrics.py    limpieza numérica, por-90, métricas derivadas
  leagues.py    coeficientes de fuerza de liga
  scoring.py    nivel, techo, irrupción  <- el modelo
  ingest.py     carga de CSV/Excel y diagnóstico
  api.py        cliente de API configurable (opcional)
  reports.py    tablas, exportación y fichas
  cli.py        línea de comandos
config/leagues.yaml   coeficientes editables
tools/make_sample.py  generador de datos sintéticos de prueba
tests/                135 tests
```

```bash
python -m pytest tests/ -q
```

Los ficheros de `data/sample/` son **sintéticos y generados al azar**: nombres,
equipos y números inventados para poder probar el sistema. No sirven para
scouting.
