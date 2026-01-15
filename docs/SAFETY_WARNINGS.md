# ⚠️ Li-ion Battery Safety Warnings

🔴 **DANGER: 18+ ONLY - ADULT SUPERVISION REQUIRED** 🔴
🔴 **DO NOT ATTEMPT WITHOUT ELECTRICAL SAFETY TRAINING** 🔴
🔴 **BATTERIES CAN EXPLODE AND CAUSE DEATH** 🔴

⚠️ ASCII Fallback: [WARNING][DANGER][FIRE RISK] - If emojis don't render, critical warnings remain visible

Li-ion batteries contain flammable electrolyte and can catch fire or explode if mishandled.

## 🔥 FIRE RISK
Li-ion batteries contain flammable electrolyte. Mishandling causes fires.

## Critical Safety Rules:
1. ✅ Check BMS polarity BEFORE connecting (reverse = explosion)
2. ✅ Never short battery terminals
3. ✅ Solder quickly (<3sec) to avoid heat damage
4. ✅ First power-on: Verify voltage with multimeter BEFORE connecting to robot
5. ✅ Keep Class D fire extinguisher nearby (Class D extinguishers are specifically designed for metal/lithium fires - water makes Li-ion fires WORSE)
6. ✅ Wear heat-resistant gloves rated for 200°C minimum when handling batteries during soldering or emergency situations

## Emergency Procedures:

### If Battery Is Smoking/Hot:
1. **DO NOT TOUCH** - Use non-conductive tongs or heat-resistant gloves (200°C rated minimum)
2. **Move to fireproof container** - Metal ammo box, ceramic pot, or metal bucket with dry sand or vermiculite (NOT plastic containers, NOT water)
3. **Evacuate area** - Li-ion fire releases toxic fumes
4. **Call emergency services** - Explain it's a lithium battery fire
5. **Use Class D fire extinguisher** - Standard ABC extinguishers won't work on lithium fires
6. **Let burn out safely** - Do not attempt to extinguish with water

### If Battery Swells:
- **DO NOT USE** - Dispose at battery recycling center immediately

### If Skin Contact With Electrolyte:
- **Flush with water for 15 minutes** - Seek medical help immediately

## Charging Safety:
- Use ONLY BMS-protected charging
- Never charge unattended
- Charge in fireproof LiPo bag

## Additional Safety Guidelines:

### Storage Safety:
- Store at 40-60% charge (3.7-3.8V per cell for storage, 3.6V is nominal operating voltage)
- Keep away from flammable materials
- Store in cool, dry place (ideal: 15-25°C, never exceed 60°C)
- Never store in direct sunlight or hot environments
- Use fireproof battery storage bag or metal container (metal ammo box recommended)

### Handling Precautions:
- Inspect batteries regularly for damage, dents, or swelling
- Never use damaged or swollen batteries
- Avoid dropping or physical impacts
- Keep batteries away from metal objects (keys, coins, tools)
- Never disassemble or puncture battery cells

### Soldering Safety:
- Use proper ventilation when soldering
- Solder tabs quickly to minimize heat transfer to cell
- Allow battery to cool between solder operations
- Monitor battery temperature during soldering (should remain cool to touch)
- If battery becomes warm during soldering, STOP and allow to cool

### Disposal:
- Never throw Li-ion batteries in regular trash
- Take to certified battery recycling center
- Tape terminals with non-conductive tape before disposal
- Check local regulations for proper disposal methods

### Warning Signs - STOP USING IMMEDIATELY IF:
- Battery is hot to touch (>45°C)
- Unusual smell (sweet or chemical odor)
- Visible swelling or deformation
- Hissing or popping sounds
- Voltage drops rapidly during use
- Battery takes unusually long to charge

## Specific Warnings for Molicel P30B:

### Specifications:
- Nominal voltage: 3.6V (typical operating voltage)
- Storage voltage: 3.7-3.8V (40-60% charge for long-term storage)
- Max charge voltage: 4.2V (fully charged)
- Min discharge voltage: 2.5V (protect below 3.0V)
- Max continuous discharge: 30A [Source: Molicel P30B Datasheet]
- Max pulse discharge: 36A [Source: Molicel P30B Datasheet]

### Operating Limits:
- Never discharge below 2.5V (BMS should cut off at 3.0V)
- Never charge above 4.2V
- Charge at max 1.5A (0.5C recommended for longevity)
- Operating temperature: -20°C to 60°C
- Charging temperature: 0°C to 45°C

### BMS (Battery Management System) Requirements:
- REQUIRED for all Li-ion applications
- Must have overcharge protection (>4.25V)
- Must have over-discharge protection (<2.8V)
- Must have short circuit protection
- Should have balance charging for multi-cell packs
- Our BMS: 20A continuous, 2S (7.2V nominal)

## 📋 Safety Standards Compliance

This project references but does not replace compliance with:

- **UN38.3** - Transport of lithium batteries
- **IEC 62133** - Safety requirements for portable sealed secondary cells
- **UL1642** - Lithium battery safety standard
- **CE Marking** - Required for EU market (if applicable)

**Note:** Users are responsible for ensuring compliance with local regulations and obtaining necessary certifications before commercial use or transport.

## Project-Specific Safety Notes:

### First Power-On Checklist:
1. Verify BMS wiring with multimeter BEFORE connecting battery
2. Measure voltage at BMS output (should be 7.2-8.4V for 2S pack)
3. Check polarity: Red = positive (+), Black = negative (-)
4. Connect load (robot) with inline fuse (3A recommended)
5. Monitor first power-on for any signs of problems

### During Operation:
- Monitor battery voltage regularly
- Never fully discharge (stop using at 6.0V for 2S pack)
- Limit continuous current to <30A (single cell) or <60A (2S parallel)
- Check battery temperature after heavy use
- Disconnect battery when not in use

### Charging Procedure:
1. Charge in fireproof LiPo bag on non-flammable surface
2. Use BMS-compatible charger (8.4V max for 2S)
3. Set charge current to 1.5A or less
4. Never leave charging unattended
5. Stop charging if battery becomes warm (>40°C)
6. Verify voltage after charging (should be 8.4V ±0.1V for 2S)

## 📞 Emergency Contacts (Italy)

**Note:** For users outside Italy, contact your local emergency services and specify "lithium battery fire" when calling.

### Italy Emergency Services:
- 🚨 **Emergency (Fire/Medical):** 112 (EU-wide emergency number, 24/7)
- 🔥 **Fire Department (Vigili del Fuoco):** 115 (direct fire emergency)
- 🏥 **Medical Emergency:** 118 (ambulance)
- ☠️ **Poison Control (Centro Antiveleni Milano):** 02 66101029

### Battery Recycling Centers (Italy):
- **Local "Isola Ecologica"** - Municipal waste center (search "isola ecologica [your city]")
- **Electronics Stores** - Many accept battery returns: MediaWorld, Euronics, Unieuro
- **Hazardous Waste Collection** - Periodic municipal collection days
- **Contact Info** - Check your municipality website or call local environmental office
- **Important** - Tape battery terminals with electrical tape before disposal to prevent short circuits
- **Search Online** - Visit www.coou.it or www.cdcraee.it for official Italian e-waste disposal locations

## ⚖️ Legal Disclaimer

**DISCLAIMER OF LIABILITY:**
This document does not constitute professional safety advice. Li-ion batteries are inherently dangerous and can cause fire, explosion, chemical burns, and death.

**BY USING THESE BATTERIES, YOU ACKNOWLEDGE AND ASSUME ALL RISKS** of injury, death, and property damage. You agree to indemnify and hold harmless all contributors, authors, and distributors from any claims, damages, or liabilities arising from battery use.

**NO WARRANTIES:** This information is provided "AS IS" without warranty of any kind, express or implied. We make no guarantees about accuracy, completeness, or fitness for any purpose.

**ADULT USE ONLY:** This project is intended for adults 18+ with electrical safety training. Children must never handle Li-ion batteries unsupervised.

**COMPLIANCE:** Users are responsible for compliance with local regulations, including UN38.3 (transport), IEC 62133 (safety), and UL1642 (lithium battery safety) standards.

**GOVERNING LAW:** This disclaimer and all safety warnings are governed by
the laws of Italy. Any disputes shall be resolved in Italian courts under
Italian jurisdiction. For users outside Italy, local consumer protection laws
and product liability regulations may supersede this disclaimer.

**When in doubt: STOP, ask for help, and consult experts.**

---

**Document Version:** 1.1
**Last Updated:** 15 January 2026
**Author:** OpenDuck Mini V3 Safety Team
**Review Status:** APPROVED

⚡ **Remember: Safety is not optional. Your life and property depend on following these guidelines.**
