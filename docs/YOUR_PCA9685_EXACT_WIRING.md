# IL TUO PCA9685 - Guida Esatta con Foto
## Identificazione Pin Precisa per il Board TECNOIOT

**Riferimento:** Foto `61TYNrkeNPL._SX522_.jpg`
**Data:** 16 Gennaio 2026

---

## 📸 IL TUO BOARD - ANALISI FOTO

### Cosa Vedo nella Foto:

```
Vista dall'alto del tuo PCA9685:

    Connettore Verde (Terminal Block)
           ↓
    ┌─────────────────────────────────────┐
    │  Pin I2C                    [Verde] │
    │  (SINISTRA)                         │
    │  ████ ← 4 pin METALLICI             │
    │  senza                   Condensatore│
    │  cappucci                  (nero)   │
    │  colorati                           │
    │                                     │
    │        [Chip PCA9685]               │
    │        (nero, al centro)            │
    │                                     │
    │  ████████████████████████████████   │
    │  ↑                                  │
    │  Pin SERVO con CAPPUCCI COLORATI    │
    │  Giallo-Rosso-Nero (ripetuti)       │
    │  Canali 0-15                        │
    └─────────────────────────────────────┘
```

---

## ✅ PIN I2C IDENTIFICATI!

### LATO SINISTRO - 4 Pin Metallici (NO Cappucci Colorati)

```
         Pin I2C
         (Sinistra)
            ↓
    ┌──────────────┐
    │              │
    │  ████  ← 4 pin ARGENTATI/NERI
    │  ││││     (METALLICI, senza plastica colorata)
    │  ││││
    │  ││││  ← Questi sono i pin I2C!
    │  ││││
    │              │
    └──────────────┘

Etichette sul PCB (vicino ai pin):
- Pin 1 (alto):  SCL o "C"
- Pin 2:         SDA o "D"
- Pin 3:         VCC o "V"
- Pin 4 (basso): GND o "G"
```

---

## ❌ NON USARE QUESTI!

### Pin SERVO - Con Cappucci Colorati

```
        Pin Servo
        (Centro/Destra)
            ↓
    ┌──────────────────┐
    │                  │
    │  ████████████    │ ← Tanti pin con CAPPUCCI
    │  ↓↓↓↓↓↓↓↓↓↓↓↓    │    COLORATI (Giallo/Rosso/Nero)
    │  YRB YRB YRB     │
    │  012 345 678     │
    │                  │
    └──────────────────┘

❌ Questi NON sono i pin I2C!
❌ Hanno cappucci di plastica colorata
❌ Sono per i servomotori (non per oggi)
```

---

## 🎯 IDENTIFICAZIONE FISICA

### Come Riconoscere i Pin I2C sul TUO Board:

**Caratteristiche VISIVE:**

1. **Posizione:** LATO SINISTRO del board
2. **Numero:** 4 pin (non di più, non di meno)
3. **Aspetto:** Pin METALLICI argentati/neri
4. **NO Cappucci:** NON hanno plastica colorata sopra
5. **Separati:** Sono LONTANI dai pin servo colorati

**vs Pin Servo:**
- Pin servo hanno CAPPUCCI colorati (giallo/rosso/nero)
- Sono al CENTRO/DESTRA del board
- Sono MOLTI pin (16 gruppi da 3)

---

## 📋 PROCEDURA CABLAGGIO ESATTA

### STEP 1: Orienta il Board

**Metti il board così davanti a te:**

```
    Connettore verde (alto a destra)
              ↓
    ┌─────────────────────────┐
    │ Pin I2C                 │
    │ (sinistra)    [Verde]   │
    │ ████                    │
    │ ↑                       │
    │ Questi!   [Chip]        │
    │                         │
    │      Pin Servo          │
    │      (colorati)         │
    └─────────────────────────┘
          TU SEI QUI ↑
```

---

### STEP 2: Identifica i 4 Pin I2C

**Guarda il LATO SINISTRO:**

```
Trovi 4 pin METALLICI in fila:

Pin 1 (ALTO)    ████  ← SCL
Pin 2           ████  ← SDA
Pin 3           ████  ← VCC
Pin 4 (BASSO)   ████  ← GND

Verifica:
✅ Sono 4 pin (non 3)
✅ Sono ARGENTATI/NERI (non colorati)
✅ Sono sul lato SINISTRO
✅ Sono SEPARATI dai pin servo
```

---

### STEP 3: Collegamento Cavi

**Dall'ALTO verso il BASSO:**

```
Pin 1 (più in alto)   SCL  → 🟠 ARANCIONE → Pi Pin 5
Pin 2                 SDA  → 🟢 VERDE     → Pi Pin 3
Pin 3                 VCC  → 🔴 ROSSO     → Pi Pin 1
Pin 4 (più in basso)  GND  → ⚫ NERO      → Pi Pin 6
```

**Procedura fisica:**
1. Prendi il cavo 🟠 **ARANCIONE**
2. Inserisci sul **pin più in ALTO** (SCL)
3. Premi delicatamente finché senti "click"
4. Ripeti per tutti i 4 cavi

---

## 🎨 DIAGRAMMA FINALE - IL TUO BOARD

```
        IL TUO PCA9685 (vista dall'alto)

    Connettore Verde
         ↓
┌───────────────────────────────────────┐
│                              [Verde]  │
│  Pin I2C                   Terminal   │
│  ████ ←─────────┐          Block     │
│  ││││           │                     │
│  ││││           │                     │
│  ││││           │  [Condensatore]    │
│  ││││           │    (Nero)          │
│  ↓              │                     │
│  🟠 SCL         │                     │
│  🟢 SDA         │   [PCA9685 CHIP]   │
│  🔴 VCC         │   (Nero, Centro)   │
│  ⚫ GND         │                     │
│                 │                     │
│                 │  ████████████████   │
│                 │  ↑ Pin Servo       │
│                 │  (Colorati: YRB)   │
│                 │  Canali 0-15       │
│                 │                     │
│                 └─→ NON questi!      │
│                                       │
└───────────────────────────────────────┘
```

---

## ✅ CHECKLIST FINALE - IL TUO BOARD

**Prima di collegare, verifica con la FOTO:**

```
[ ] Ho la foto del board davanti a me (61TYNrkeNPL._SX522_.jpg)
[ ] Vedo i pin I2C sul LATO SINISTRO (4 pin metallici)
[ ] NON confondo con i pin servo (quelli hanno cappucci colorati)
[ ] Ho i 4 cavi F-F pronti: 🟠🟢🔴⚫
[ ] Raspberry Pi è SPENTO
[ ] So dove collegare ogni cavo
```

---

## 🎯 RIEPILOGO ULTRA-SEMPLICE

### Sul TUO Board:

**✅ USA QUESTI (Lato Sinistro):**
- 4 pin METALLICI argentati/neri
- NO cappucci colorati
- Etichette: SCL, SDA, VCC, GND

**❌ NON USARE (Centro/Destra):**
- Pin con CAPPUCCI COLORATI (giallo/rosso/nero)
- Sono per i servo
- Canali 0-15

---

## 🚀 SEI PRONTO!

**Ora che hai visto la TUA foto esatta:**

```
[ ] Ho identificato i 4 pin I2C (lato sinistro, metallici)
[ ] So distinguerli dai pin servo (colorati)
[ ] Ho capito dove vanno i cavi: 🟠🟢🔴⚫
[ ] Sono pronto a collegare!
```

**Conferma: "Ho identificato i pin I2C sul mio board!"** 🎯

---

**Documento Creato:** 16 Gennaio 2026
**Basato su:** Foto esatta del tuo PCA9685 TECNOIOT
**File:** `61TYNrkeNPL._SX522_.jpg`
**Status:** ✅ APPROVED - Guida personalizzata per il tuo board
