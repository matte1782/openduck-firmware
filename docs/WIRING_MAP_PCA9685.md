# PCA9685 Wiring Map - Official Project Standard
## Data: 16 Gennaio 2026

**IMPORTANTE:** Questa è la mappatura UFFICIALE dei colori per tutti i collegamenti PCA9685.
Usare sempre questi colori per coerenza e debugging facile.

---

## 🎨 MAPPATURA COLORI UFFICIALE

### PCA9685 → Raspberry Pi I2C

| Cavo | Funzione | Da (PCA9685) | A (Raspberry Pi) | Tensione/Segnale |
|------|----------|--------------|------------------|------------------|
| 🔴 **ROSSO** | Alimentazione | VCC | Pin 1 (3.3V) | 3.3V Power |
| ⚫ **NERO** | Ground | GND | Pin 6 (GND) | 0V Ground |
| 🟢 **VERDE** | I2C Data | SDA | Pin 3 (GPIO2) | I2C SDA |
| 🟠 **ARANCIONE** | I2C Clock | SCL | Pin 5 (GPIO3) | I2C SCL |

---

## 📊 DIAGRAMMA VISIVO CON COLORI ESATTI

```
    PCA9685 Board                    Raspberry Pi 4
    ┌─────────────┐                  ┌──────────────┐
    │             │                  │              │
    │  VCC ●──────┼────🔴 ROSSO ─────┼──● Pin 1     │ 3.3V
    │             │                  │              │
    │  GND ●──────┼────⚫ NERO ───────┼──● Pin 6     │ GND
    │             │                  │              │
    │  SDA ●──────┼────🟢 VERDE ─────┼──● Pin 3     │ GPIO2/SDA
    │             │                  │              │
    │  SCL ●──────┼────🟠 ARANCIONE ─┼──● Pin 5     │ GPIO3/SCL
    │             │                  │              │
    │  V+  ○ VUOTO│                  │              │
    │  GND ○ VUOTO│                  │ [USB-C]──────┼─── Power
    └─────────────┘                  └──────────────┘
```

---

## 🔍 VISTA DETTAGLIATA PER PIN

### Pin PCA9685 (4-pin I2C header):
```
┌─────────────────────────────┐
│  PCA9685 I2C Connection     │
│                             │
│  Pin 1: VCC  ●──🔴 ROSSO    │
│  Pin 2: GND  ●──⚫ NERO     │
│  Pin 3: SDA  ●──🟢 VERDE    │
│  Pin 4: SCL  ●──🟠 ARANCIONE│
│                             │
└─────────────────────────────┘
```

### Pin Raspberry Pi GPIO:
```
┌─────────────────────────────┐
│  Raspberry Pi 4 GPIO        │
│  (Vista dall'alto)          │
│                             │
│  Pin 1 (3.3V)   [●]──🔴     │
│  Pin 2 (5V)     [●]         │
│  Pin 3 (GPIO2)  [●]──🟢     │
│  Pin 4 (5V)     [●]         │
│  Pin 5 (GPIO3)  [●]──🟠     │
│  Pin 6 (GND)    [●]──⚫     │
│  Pin 7 (GPIO4)  [●]         │
│  ...                        │
└─────────────────────────────┘
```

---

## 📋 CHECKLIST VISIVA PER CABLAGGIO

### Prima di collegare (Raspberry Pi SPENTO):
- [ ] Ho i 4 cavi F-F: Rosso, Nero, Verde, Arancione
- [ ] Raspberry Pi è SPENTO (USB-C scollegato)
- [ ] Workspace sicuro pronto

### Ordine di collegamento consigliato:

#### STEP 1: Cavo ROSSO 🔴
```
Da: PCA9685 pin "VCC" (primo pin del gruppo I2C)
A:  Raspberry Pi "Pin 1" (angolo in alto a sinistra, 3.3V)
[ ] Collegato e inserito completamente
```

#### STEP 2: Cavo NERO ⚫
```
Da: PCA9685 pin "GND" (secondo pin del gruppo I2C)
A:  Raspberry Pi "Pin 6" (terza fila, lato sinistro, GND)
[ ] Collegato e inserito completamente
```

#### STEP 3: Cavo VERDE 🟢
```
Da: PCA9685 pin "SDA" (terzo pin del gruppo I2C)
A:  Raspberry Pi "Pin 3" (seconda fila, lato sinistro, GPIO2)
[ ] Collegato e inserito completamente
```

#### STEP 4: Cavo ARANCIONE 🟠
```
Da: PCA9685 pin "SCL" (quarto pin del gruppo I2C)
A:  Raspberry Pi "Pin 5" (terza fila, lato sinistro, GPIO3)
[ ] Collegato e inserito completamente
```

---

## ✅ VERIFICA FINALE PRE-ACCENSIONE

### Checklist Colori:
```
PCA9685 Side:
[ ] VCC → 🔴 ROSSO collegato
[ ] GND → ⚫ NERO collegato
[ ] SDA → 🟢 VERDE collegato
[ ] SCL → 🟠 ARANCIONE collegato

Raspberry Pi Side:
[ ] Pin 1 (3.3V) → 🔴 ROSSO collegato
[ ] Pin 6 (GND)  → ⚫ NERO collegato
[ ] Pin 3 (GPIO2)→ 🟢 VERDE collegato
[ ] Pin 5 (GPIO3)→ 🟠 ARANCIONE collegato
```

### Verifica Sicurezza:
```
[ ] Tutti i 4 cavi inseriti completamente
[ ] Nessun filo esposto tocca altri pin
[ ] V+ e GND (servo power) VUOTI sul PCA9685
[ ] Raspberry Pi ancora SPENTO
[ ] Nessun cavo allentato
```

---

## 🎯 STANDARD PROGETTO

**Questa mappatura è UFFICIALE per:**
- ✅ Day 6 testing (oggi)
- ✅ Week 02 hardware integration
- ✅ Tutti i futuri setup PCA9685
- ✅ Documentazione e troubleshooting

**Benefici:**
1. **Coerenza:** Sempre gli stessi colori = meno errori
2. **Debug rapido:** Se SDA non funziona, cerco il cavo VERDE
3. **Manutenzione:** Chiunque può seguire lo standard
4. **Foto documentazione:** Colori riconoscibili

---

## 📸 NOTE PER FOTO DOCUMENTAZIONE

Quando scatti foto del setup:
- Assicurati che i colori dei cavi siano visibili
- Fai foto da angolazioni multiple (top view, side view)
- Salva in: `assets/photos/progress/day_06_pca9685_wiring.jpg`

---

## 🔧 TROUBLESHOOTING PER COLORE

| Problema | Cavo da Controllare | Cosa Verificare |
|----------|---------------------|-----------------|
| I2C non rileva 0x40 | 🔴 ROSSO, ⚫ NERO | Alimentazione |
| I2C error "No such device" | 🟢 VERDE, 🟠 ARANCIONE | Connessioni I2C |
| Board non si accende | 🔴 ROSSO → Pin 1 corretto? | Verifica 3.3V |
| Lettura dati instabile | 🟢 VERDE → Pin 3? | Verifica SDA |
| Clock error | 🟠 ARANCIONE → Pin 5? | Verifica SCL |

---

## 📝 STORICO REVISIONI

| Data | Versione | Modifiche |
|------|----------|-----------|
| 16 Gen 2026 | 1.0 | Mappatura iniziale Day 6 |

---

**Documento Creato:** 16 Gennaio 2026
**Autore:** Matteo Panzeri + Claude AI
**Status:** ✅ APPROVED - Official Project Standard
**File:** `firmware/docs/WIRING_MAP_PCA9685.md`
