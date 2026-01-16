# PCA9685 Physical Layout Guide
## Come Orientare e Identificare i Pin

---

## 🔍 ORIENTAMENTO DEL BOARD

### Vista dall'Alto (Board su Tavolo):

```
    ┌─────────────────────────────────────────────────────────┐
    │                                                           │
    │                    PCA9685 BOARD                         │
    │                   (Vista dall'alto)                      │
    │                                                           │
    │  Pin I2C (4 pin):                                        │
    │  ┌───┐ ┌───┐ ┌───┐ ┌───┐   ← Pin header VERTICALI       │
    │  │ █ │ │ █ │ │ █ │ │ █ │      (sporgono VERSO L'ALTO)   │
    │  └───┘ └───┘ └───┘ └───┘                                │
    │  VCC   GND   SDA   SCL                                   │
    │                                                           │
    │         ┌──────────────┐                                 │
    │         │  PCA9685     │  ← Chip principale              │
    │         │   CHIP       │                                 │
    │         └──────────────┘                                 │
    │                                                           │
    │  Servo Channels (16 canali):                            │
    │  ┌───┐┌───┐┌───┐  ┌───┐┌───┐┌───┐                      │
    │  │ █ ││ █ ││ █ │  │ █ ││ █ ││ █ │  ← Pin verticali      │
    │  └───┘└───┘└───┘  └───┘└───┘└───┘                      │
    │   0     1    2      ...   14   15                       │
    │                                                           │
    │  V+ / GND (Power):                                       │
    │  ┌───┐ ┌───┐   ← Pin verticali                          │
    │  │ █ │ │ █ │                                            │
    │  └───┘ └───┘                                            │
    │   V+   GND                                               │
    │                                                           │
    └─────────────────────────────────────────────────────────┘
```

---

## 📐 VISTA LATERALE (Importante!)

### Come Appaiono i Pin di Lato:

```
                   ┌─ Pin sporgono VERSO L'ALTO
                   │
                   ▼
             ┌───┐ ┌───┐ ┌───┐ ┌───┐
             │ █ │ │ █ │ │ █ │ │ █ │  ← Pin header MASCHI
             └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘     (verticali, ~10mm altezza)
               │     │     │     │
    ═══════════╪═════╪═════╪═════╪═══════════
    ║          │     │     │     │          ║
    ║    ┌─────┴─────┴─────┴─────┴─────┐   ║
    ║    │    PCA9685 PCB Board        │   ║  ← Board (piatto)
    ║    └──────────────────────────────┘   ║
    ═══════════════════════════════════════════
         ^
         │
         └─ Tavolo (superficie)
```

**Risposta:** I pin sono **VERTICALI** - sporgono **VERSO L'ALTO** dal board!

---

## 🎯 COME IDENTIFICARE I PIN I2C

### Step 1: Trova il Gruppo I2C

**Caratteristiche:**
- **4 pin consecutivi** (non 3 come i servo)
- Di solito in un **angolo** del board
- Etichette vicine: "VCC GND SDA SCL" o "V G D C"
- A volte scritto "I2C" vicino

```
Cerca questo pattern (4 pin insieme):
┌───┐ ┌───┐ ┌───┐ ┌───┐
│   │ │   │ │   │ │   │  ← 4 pin (NON 3!)
└───┘ └───┘ └───┘ └───┘
VCC   GND   SDA   SCL
```

**NON confondere con:**
```
Servo channels (3 pin):
┌───┐ ┌───┐ ┌───┐
│   │ │   │ │   │  ← Solo 3 pin
└───┘ └───┘ └───┘
 S    V+   GND
```

---

## 🔌 COME COLLEGARE I CAVI F-F

### I Pin Sono VERTICALI (Maschi):

```
Vista 3D del collegamento:

    Cavo Dupont F-F
    (Femmina-Femmina)
         │
         │   ┌────────┐
         └───┤ Cavità │  ← Connettore FEMMINA del cavo
             │   ○    │
             └────┬───┘
                  │
                  ▼
             ┌────┴────┐
             │    █    │  ← Pin MASCHIO del PCA9685
             └────┬────┘     (verticale, sporge verso l'alto)
                  │
         ═════════╪══════════
         ║        │        ║
         ║   PCA9685 Board ║
         ║                 ║
         ════════════════════
```

**Procedura:**
1. Prendi il cavo F-F
2. **Guarda il pin del PCA9685** (sporge verso l'alto, come un chiodino)
3. **Posiziona il connettore FEMMINA sopra il pin**
4. **Premi delicatamente verso il basso**
5. Sentirai un "click" quando è inserito completamente

---

## 📋 ORIENTAMENTO CORRETTO PER CABLAGGIO

### Posiziona il PCA9685 sul Tavolo:

```
Orientamento consigliato:

┌─────────────────────────────────────┐
│                                     │
│        PCA9685 Board                │
│                                     │
│  Pin I2C (4 pin)                   │
│  ↓ ↓ ↓ ↓  ← Questi pin verso di TE│
│  █ █ █ █                           │
│  V G D C                           │
│                                     │
│  [Grande Chip Nero]                │
│                                     │
│  Servo 0-15 (dall'altra parte)    │
│                                     │
└─────────────────────────────────────┘
         ^
         │
      TU SEI QUI (guardando il board)
```

**Consigli:**
1. **Metti il board piatto sul tavolo**
2. **Orienta i pin I2C verso di te**
3. **I pin sporgono verso l'alto** (li vedi come "chiodini")
4. **Collega i cavi dall'alto verso il basso**

---

## ✅ CHECKLIST IDENTIFICAZIONE

Prima di collegare, verifica:

```
[ ] PCA9685 è piatto sul tavolo
[ ] Vedo i pin I2C (4 pin consecutivi)
[ ] Pin sporgono VERSO L'ALTO (verticali)
[ ] So distinguere: VCC, GND, SDA, SCL
[ ] Ho i cavi F-F pronti (4 cavi con cavità alle estremità)
[ ] Capisco che collego i cavi DALL'ALTO sui pin
```

---

## 🎨 DOVE SONO LE ETICHETTE?

### Sul PCA9685 Board:

**Etichette stampate sul PCB:**
- Di solito **VICINO** ai pin (non sopra)
- Scritte bianche su board blu/nero
- Formato: "VCC GND SDA SCL" oppure "V G D C"

```
Esempio layout etichette:

    █  █  █  █    ← Pin verticali
    │  │  │  │
┌───┴──┴──┴──┴────┐
│                  │
│ VCC GND SDA SCL  │ ← Etichette stampate sul board
│                  │
└──────────────────┘
```

---

## 🔍 FOTO MENTALE - COME DEVE APPARIRE

### Setup Finale (Vista dall'Alto):

```
    PCA9685                      Raspberry Pi
    ┌──────┐                     ┌─────────┐
    │      │                     │         │
    │  █ ──┼────🔴 ROSSO────────┤         │
    │  █ ──┼────⚫ NERO─────────┤         │
    │  █ ──┼────🟢 VERDE────────┤ GPIO    │
    │  █ ──┼────🟠 ARANCIONE────┤ Header  │
    │      │                     │         │
    └──────┘                     └─────────┘

    ↑ Pin verticali              ↑ Pin verticali
    (sporgono su)                (sporgono su)
```

---

## 🎯 RIASSUNTO ORIENTAMENTO

| Domanda | Risposta |
|---------|----------|
| Pin di lato o sopra? | **SOPRA** (verticali) |
| Come appaiono? | Come piccoli "chiodini" metallici |
| Come collego i cavi? | Dall'alto verso il basso |
| Dove sono le etichette? | Stampate sul PCB vicino ai pin |
| Quanti pin I2C? | **4 pin** (VCC, GND, SDA, SCL) |
| Come li riconosco? | Gruppo di 4 pin (non 3 come servo) |

---

**Documento Creato:** 16 Gennaio 2026
**Status:** ✅ APPROVED
