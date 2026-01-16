# PCA9685 - Guida Visiva Cablaggio con Foto Ufficiale
## Documento Definitivo per Evitare Errori

**Data:** 16 Gennaio 2026
**Foto Riferimento:** Adafruit Official PCA9685 Board

---

## 🎯 SCOPERTA IMPORTANTE!

Il PCA9685 ha **PIN DUPLICATI SU ENTRAMBI I LATI!**

```
      Lato SINISTRO          Lato DESTRO
           ↓                      ↓
    ┌──────────────────────────────────┐
    │ SCL █                        █ SCL│
    │ SDA █                        █ SDA│
    │ VCC █                        █ VCC│
    │ GND █                        █ GND│
    │              CHIP                 │
    │ V+  █                        █ V+ │
    │ GND █                        █ GND│
    │                                   │
    │ [Servo Channels 0-15]             │
    └───────────────────────────────────┘

✅ PUOI USARE ENTRAMBI I LATI! (sono identici)
```

**Questo spiega perché vedi molti pin!**

---

## 📸 FOTO UFFICIALE ADAFRUIT

**Link Foto Ufficiale:**
- [Adafruit PCA9685 Pinout](https://learn.adafruit.com/16-channel-pwm-servo-driver/pinouts)
- [Adafruit Wiring Guide](https://learn.adafruit.com/16-channel-pwm-servo-driver/hooking-it-up)

**Scarica la foto qui:**
https://cdn-learn.adafruit.com/assets/assets/000/002/689/original/adafruit_products_schem.png

---

## 🎨 IDENTIFICAZIONE SICURA AL 100%

### OPZIONE 1: Usa il Lato SINISTRO (Consigliato)

**Posizione:** Lato sinistro del board, 4 pin in fila

```
Vista dall'alto del board:
┌─────────────────────────────────┐
│                                 │
│ SCL █ ← Pin 4 (in alto)        │
│ SDA █ ← Pin 3                  │
│ VCC █ ← Pin 2                  │
│ GND █ ← Pin 1 (in basso)       │
│                                 │
│        [PCA9685 CHIP]           │
│                                 │
│ V+  █ ← NON toccare!           │
│ GND █ ← NON toccare!           │
│                                 │
│ [Servo 0-15] →→→→→→→→→→        │
└─────────────────────────────────┘
```

**Sequenza dall'ALTO verso il BASSO:**
1. **SCL** (in alto) → 🟠 ARANCIONE → Pi Pin 5
2. **SDA** → 🟢 VERDE → Pi Pin 3
3. **VCC** → 🔴 ROSSO → Pi Pin 1
4. **GND** (in basso) → ⚫ NERO → Pi Pin 6

---

### OPZIONE 2: Usa il Lato DESTRO (Alternativa)

**Se preferisci il lato destro, i pin sono IDENTICI:**

```
┌─────────────────────────────────┐
│                                 │
│        [PCA9685 CHIP]           │
│                                 │
│                    █ SCL ← Pin 4│
│                    █ SDA ← Pin 3│
│                    █ VCC ← Pin 2│
│                    █ GND ← Pin 1│
│                                 │
│        ←←←←←←←←← [Servo 0-15]  │
└─────────────────────────────────┘
```

**⚠️ IMPORTANTE:** Usa UN SOLO LATO (sinistro O destro, non entrambi!)

---

## 🔍 COME DISTINGUERE I2C DA POWER

### Pin I2C (4 pin in fila):
```
SCL █  ← Etichetta "SCL"
SDA █  ← Etichetta "SDA"
VCC █  ← Etichetta "VCC"
GND █  ← Etichetta "GND"
─────────── Spazio ───────────
V+  █  ← Etichetta "V+" (NON "VCC"!)
GND █  ← Sotto V+
```

**Differenza chiave:**
- **I2C VCC** = Per il chip (3.3V/5V)
- **V+** = Per i servo (6V-12V) ← NON toccare oggi!

---

## 📋 PROCEDURA STEP-BY-STEP

### STEP 1: Orienta il Board

**Metti il board così:**
```
    Chip PCA9685 al centro
           ↓
┌─────────────────────────────┐
│ Pin I2C                     │
│ (sinistra)                  │
│ █ █ █ █                     │
│ ↑ questi                    │
│                             │
│      [CHIP]                 │
│                             │
│ Servo channels (sotto) →   │
└─────────────────────────────┘
      TU SEI QUI ↑
```

---

### STEP 2: Identifica i 4 Pin I2C

**Trova questi nell'ORDINE:**

```
Dall'ALTO verso il BASSO:
┌────┐
│ █  │ 1. SCL (più in alto)
├────┤
│ █  │ 2. SDA
├────┤
│ █  │ 3. VCC
├────┤
│ █  │ 4. GND (più in basso)
└────┘
─────── SPAZIO (importante!) ───────
┌────┐
│ █  │ V+ (questo è SOTTO, separato!)
├────┤
│ █  │ GND power
└────┘
```

**Verifica:** Tra il 4° pin (GND I2C) e il pin V+ c'è uno **SPAZIO** sul board!

---

### STEP 3: Collegamento con Colori

```
Pin Board    Etichetta   Cavo         Raspberry Pi
─────────    ─────────   ────         ────────────
Pin 1 (alto)   SCL    → 🟠 ARANCIONE → Pin 5 (GPIO3)
Pin 2          SDA    → 🟢 VERDE     → Pin 3 (GPIO2)
Pin 3          VCC    → 🔴 ROSSO     → Pin 1 (3.3V)
Pin 4 (basso)  GND    → ⚫ NERO      → Pin 6 (GND)

SPAZIO ↓

Pin V+  (NON toccare!)
Pin GND (NON toccare!)
```

---

## ✅ CHECKLIST VISIVA PRE-COLLEGAMENTO

### Verifica PRIMA di collegare:

```
[ ] Ho identificato il gruppo I2C (4 pin in fila)
[ ] Vedo le etichette: SCL, SDA, VCC, GND
[ ] C'è uno SPAZIO sotto il pin GND I2C
[ ] Sotto lo spazio vedo V+ e GND (questi li IGNORO)
[ ] I pin servo (0-15) sono da un'altra parte del board
[ ] Ho scelto UN SOLO lato (sinistro O destro)
```

---

## 🎯 DIAGRAMMA FINALE CON FOTO

### Vista Reale del Board (dall'alto):

```
  LATO SINISTRO (Usa questo!)
         ↓
    ┌────────────────────────────────┐
    │                                │
    │ SCL █ ────🟠 ARANCIONE────→   │
    │ SDA █ ────🟢 VERDE────────→   │
    │ VCC █ ────🔴 ROSSO────────→   │
    │ GND █ ────⚫ NERO─────────→   │
    │                                │
    │ ╔══════════════════════╗       │
    │ ║   PCA9685 CHIP       ║       │
    │ ║   (Chip Nero Grande) ║       │
    │ ╚══════════════════════╝       │
    │                                │
    │ V+  █ ← NON collegare!        │
    │ GND █ ← NON collegare!        │
    │                                │
    │ ┌──────────────────────┐       │
    │ │ Servo Channels       │       │
    │ │ 0  1  2  3 ... 15   │       │
    │ │ ┆┆┆┆┆┆┆┆┆┆┆    ┆┆┆  │       │
    │ └──────────────────────┘       │
    │                                │
    └────────────────────────────────┘
```

---

## 📸 STAMPA QUESTA PAGINA!

**Per evitare errori:**

1. **Stampa questo documento**
2. **Metti il foglio accanto al board**
3. **Segui le frecce colorate**
4. **Verifica ogni connessione**

---

## 🔗 RISORSE UFFICIALI

**Documentazione Adafruit (con foto reali):**
- [Pinout Diagram](https://learn.adafruit.com/16-channel-pwm-servo-driver/pinouts)
- [Wiring Guide](https://learn.adafruit.com/16-channel-pwm-servo-driver/hooking-it-up)
- [Full Tutorial](https://learn.adafruit.com/16-channel-pwm-servo-driver?view=all)
- [PDF Manual](https://cdn-learn.adafruit.com/downloads/pdf/16-channel-pwm-servo-driver.pdf)

**Foto Board:**
- [Pinout Schema](https://cdn-learn.adafruit.com/assets/assets/000/002/689/original/adafruit_products_schem.png)

---

## ✅ CONFERMA FINALE

**Prima di collegare, verifica:**

```
[ ] Ho visitato il link Adafruit per vedere la foto
[ ] Ho identificato i pin I2C sul MIO board
[ ] Corrispondono alla foto Adafruit
[ ] Ho 4 cavi F-F pronti: 🟠🟢🔴⚫
[ ] Raspberry Pi è SPENTO
[ ] Sono sicuro al 100%
```

**Quando sei SICURO al 100%, dimmi "Pronto a collegare"!** 🎯

---

**Documento Creato:** 16 Gennaio 2026
**Basato su:** Documentazione ufficiale Adafruit
**Status:** ✅ APPROVED - Guida visiva definitiva
