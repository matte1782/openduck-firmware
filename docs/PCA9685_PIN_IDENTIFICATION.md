# PCA9685 - Guida Identificazione Pin
## Come NON Confondere i Pin I2C con i Pin Servo

---

## 🔍 IL PROBLEMA: Troppi Pin!

Il PCA9685 ha **MOLTI** gruppi di pin:
- ✅ **4 pin I2C** (VCC, GND, SDA, SCL) ← **QUESTI CI SERVONO!**
- ❌ **48 pin servo** (16 canali × 3 pin) ← NON questi!
- ❌ **2-4 pin power** (V+, GND per servomotori) ← NON questi!

**Totale:** ~54 pin sul board! 😵

---

## 🎯 LAYOUT COMPLETO PCA9685

### Vista Dall'Alto (Tutti i Pin):

```
┌─────────────────────────────────────────────────────────────┐
│                    PCA9685 BOARD                             │
│                                                               │
│  ╔══════════════════════════╗                                │
│  ║ PIN I2C (4 pin)          ║  ← QUESTI CI SERVONO!         │
│  ║ ┌───┐┌───┐┌───┐┌───┐    ║                                │
│  ║ │ █ ││ █ ││ █ ││ █ │    ║                                │
│  ║ └───┘└───┘└───┘└───┘    ║                                │
│  ║ VCC  GND  SDA  SCL       ║                                │
│  ╚══════════════════════════╝                                │
│                                                               │
│              ┌──────────────┐                                │
│              │  PCA9685     │  ← Chip                       │
│              │   CHIP       │                                │
│              └──────────────┘                                │
│                                                               │
│  ┌─────────────────────────────────────────┐                │
│  │ SERVO CHANNELS (16 canali × 3 pin)     │ ← NON questi!  │
│  │                                         │                 │
│  │ Chan 0  Chan 1  Chan 2  ...  Chan 15  │                 │
│  │ ┌─┬─┬─┐ ┌─┬─┬─┐ ┌─┬─┬─┐     ┌─┬─┬─┐  │                 │
│  │ │█│█│█│ │█│█│█│ │█│█│█│ ... │█│█│█│  │                 │
│  │ └─┴─┴─┘ └─┴─┴─┘ └─┴─┴─┘     └─┴─┴─┘  │                 │
│  │ YRB     YRB     YRB         YRB        │                 │
│  │ 012     012     012         012        │                 │
│  └─────────────────────────────────────────┘                │
│  Y=Giallo(Signal) R=Rosso(V+) B=Nero(GND)                   │
│                                                               │
│  ┌────────────────┐                                          │
│  │ POWER (servo)  │  ← NON questi!                          │
│  │ ┌───┐┌───┐     │                                          │
│  │ │ █ ││ █ │     │                                          │
│  │ └───┘└───┘     │                                          │
│  │  V+   GND      │                                          │
│  └────────────────┘                                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚨 COME DISTINGUERE I PIN I2C

### Caratteristiche UNICHE dei Pin I2C:

| Caratteristica | Pin I2C ✅ | Pin Servo ❌ |
|----------------|------------|--------------|
| **Numero pin** | **4 pin** consecutivi | **3 pin** per canale |
| **Etichette** | VCC, GND, SDA, SCL | Signal, V+, GND oppure 0, 1, 2 |
| **Colori stampati** | Di solito NO colori | Spesso Giallo, Rosso, Nero |
| **Posizione** | Separati, spesso in angolo | File ordinate 0-15 |
| **Dimensione gruppo** | 1 gruppo da 4 | 16 gruppi da 3 |

---

## 📋 IDENTIFICAZIONE STEP-BY-STEP

### STEP 1: Conta i Pin per Gruppo

**Prendi il board e guarda attentamente:**

```
Se vedi questo (3 pin insieme):
┌───┐┌───┐┌───┐
│ █ ││ █ ││ █ │  ← 3 pin = SERVO CHANNEL
└───┘└───┘└───┘
❌ NON sono i pin I2C!


Se vedi questo (4 pin insieme):
┌───┐┌───┐┌───┐┌───┐
│ █ ││ █ ││ █ ││ █ │  ← 4 pin = I2C
└───┘└───┘└───┘└───┘
✅ QUESTI sono i pin I2C!
```

**Procedura:**
1. Guarda ogni gruppo di pin sul board
2. **Conta i pin in ogni gruppo:** 3 o 4?
3. **Trova il gruppo con 4 pin consecutivi**
4. Quello è il gruppo I2C!

---

### STEP 2: Cerca le Etichette

**Pin I2C hanno etichette specifiche:**

```
Cerca queste parole stampate sul PCB:
✅ "VCC" o "V" o "3.3V"
✅ "GND" o "G"
✅ "SDA" o "D" o "DA"
✅ "SCL" o "C" o "CL"

OPPURE cerca:
✅ "I2C" scritto vicino ai pin
```

**NON confondere con:**
```
❌ "V+" (questo è per i servo, non I2C VCC)
❌ "GND" vicino a "V+" (questo è per i servo)
❌ Numeri: 0, 1, 2, 3... 15 (questi sono i canali servo)
❌ "Signal", "PWM", "S" (questi sono pin servo)
```

---

### STEP 3: Verifica Posizione

**I pin I2C sono di solito:**

```
OPZIONE A: In un angolo
┌─────────────────┐
│ █ █ █ █         │ ← I2C qui (4 pin isolati)
│ VCC G D C       │
│                 │
│   [Chip]        │
│                 │
│ [Servo 0-15]    │
└─────────────────┘


OPZIONE B: Su un lato
┌─────────────────┐
│                 │
│ █ █ █ █  I2C   │ ← I2C qui (4 pin su un lato)
│ V G D C         │
│   [Chip]        │
│                 │
│ [Servo 0-15]    │
└─────────────────┘
```

**NON sono mai:**
- In mezzo ai canali servo
- Mescolati con altri pin

---

## 🎨 COLORI STAMPATI SUL PCB

### Pin Servo (Colori):

```
Spesso i canali servo hanno COLORI stampati:

Chan 0:
┌───┐┌───┐┌───┐
│ █ ││ █ ││ █ │
└───┘└───┘└───┘
 Y    R    B      ← Giallo, Rosso, Nero (stampati)
 │    │    │
Signal V+  GND
```

### Pin I2C (NO Colori):

```
I pin I2C di solito hanno solo LETTERE:

┌───┐┌───┐┌───┐┌───┐
│ █ ││ █ ││ █ ││ █ │
└───┘└───┘└───┘└───┘
VCC  GND  SDA  SCL   ← Solo lettere (no colori)
```

---

## ✅ CHECKLIST IDENTIFICAZIONE

**Verifica TUTTE queste caratteristiche:**

```
[ ] Ho trovato un gruppo di 4 pin consecutivi (non 3)
[ ] Vicino ai pin vedo scritto: VCC, GND, SDA, SCL
[ ] I pin sono SEPARATI dai canali servo
[ ] NON vedo numeri tipo 0, 1, 2, 3... (quelli sono servo)
[ ] NON vedo colori Giallo/Rosso/Nero stampati (quelli sono servo)
[ ] Possibilmente vedo scritto "I2C" vicino
```

**Se hai verificato TUTTO:** ✅ Hai trovato i pin I2C corretti!

---

## 🔍 FOTO MENTALE - COSA CERCARE

### I Pin I2C Sembrano Così:

```
    Gruppo ISOLATO di 4 pin
           ↓
    ┌──────────────────┐
    │ █  █  █  █       │  ← 4 pin, NO altri pin vicini
    │ │  │  │  │       │
    │ V  G  D  C       │  ← Lettere chiare
    │ C  N  A  L       │
    │ C  D           │
    └──────────────────┘
         ↑
    Separati dagli altri pin!
```

### I Pin Servo Sembrano Così:

```
    File ordinate di gruppi da 3
           ↓
    ┌──────────────────────────┐
    │ 0   1   2   3 ...  15    │  ← Numeri
    │ ┆┆┆ ┆┆┆ ┆┆┆ ┆┆┆     ┆┆┆  │  ← 3 pin per gruppo
    │ YRB YRB YRB YRB ... YRB  │  ← Colori
    └──────────────────────────┘
         ↑
    16 gruppi identici!
```

---

## 🎯 PROCEDURA RAPIDA

1. **Guarda il board intero**
2. **Trova gruppi da 4 pin** (non 3)
3. **Leggi le etichette** vicino ai pin
4. **Cerca:** VCC, GND, SDA, SCL
5. **Evita:** Gruppi da 3 pin con numeri o colori

**Quando trovi 4 pin con VCC/GND/SDA/SCL:**
✅ **QUELLI sono i pin I2C!**

---

## 📸 SE HAI DUBBI

**Puoi:**
1. Fare una foto del board
2. Cercare "PCA9685 pinout" su Google Images
3. Confrontare con la tua board

**OPPURE:**
- Descrivi cosa vedi esattamente
- Ti aiuto a identificare i pin corretti!

---

**Documento Creato:** 16 Gennaio 2026
**Scopo:** Identificazione sicura pin I2C su PCA9685
