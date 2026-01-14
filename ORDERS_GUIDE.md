# CRITICAL ORDERS - EXECUTION GUIDE
## 15 January 2026 - Complete Before 01:30

**Time Required:** 45 minutes
**Critical Path:** FE-URT-1 has 15-25 day lead time

---

## ORDER 1: FE-URT-1 SERVO CONTROLLER ⚡ HIGHEST PRIORITY

**Why Critical:** 15-25 day shipping. STS3215 servos arriving in ~3 weeks. If not ordered tonight = 25-day gap when servos arrive = wasted February.

### Step-by-Step Execution:

1. **Open Browser:** https://www.aliexpress.com

2. **Search:** "FE-URT-1 servo controller"
   - Alternative search: "Feetech UART controller"
   - Alternative search: "FE-URT-1 serial bus servo"

3. **Filter Results:**
   - Click "Sort by: Orders" (find popular sellers)
   - Look for:
     - ✅ Seller rating >95%
     - ✅ >100 orders
     - ✅ Free/cheap shipping option
     - ✅ Product images showing actual FE-URT-1 board

4. **Select Product:**
   - Verify it's FE-URT-1 (not FE-URT-01 or other models)
   - Check product description mentions:
     - "UART/TTL control"
     - "Compatible with STS/SCS series servos"
     - "PC software included"

5. **Add to Cart:**
   - Quantity: **1 unit**
   - Price check: Should be ~€45-55

6. **Shipping Selection:**
   - **Standard Shipping** is fine (15-25 days acceptable)
   - Do NOT pay for express (not needed)
   - Destination: Italy

7. **Checkout:**
   - Enter/verify shipping address
   - Payment method: Credit card / PayPal
   - **IMPORTANT:** Save order number and tracking link

8. **Documentation:**
   - Email yourself order confirmation
   - Save tracking number to: `OPENDUCK_V3_FINAL_TRACKER.xlsx`
   - Note: "FE-URT-1 ordered 15/01/2026, ETA 30/01-10/02"

**Expected Cost:** €45-55
**Expected Arrival:** 30 Jan - 10 Feb (acceptable, servos won't arrive sooner)

**Success Check:**
- [ ] Order confirmed
- [ ] Tracking number saved
- [ ] Tracker updated

---

## ORDER 2: MOLICEL P30B BATTERIES (4 cells)

**Why Needed:** Power system testing, blocks all high-current servo tests

### Option A: Local Vape Shops (TOMORROW MORNING)

**Action Tonight:** Prepare shop list for tomorrow 09:00 calls

1. **Google Maps Search:** "Negozio sigarette elettroniche Monza"
2. **Find 5 shops:**
   - [ ] Shop 1: ___________ (Address: ___________) Phone: ___________
   - [ ] Shop 2: ___________ (Address: ___________) Phone: ___________
   - [ ] Shop 3: ___________ (Address: ___________) Phone: ___________
   - [ ] Shop 4: ___________ (Address: ___________) Phone: ___________
   - [ ] Shop 5: ___________ (Address: ___________) Phone: ___________

3. **Tomorrow 09:00:** Call each shop, ask:
   - "Buongiorno, avete batterie Molicel INR18650-P30B?"
   - If YES: "Quante ne avete? Ho bisogno di 4 celle."
   - Note address, drive immediately to acquire

**Cost:** €14-16 (4 cells × €3.50-4.00)

### Option B: Online Order (BACKUP - Do Tonight if Impatient)

**Website:** https://www.thebatteryshop.eu/

1. **Search:** "Molicel INR18650-P30B"
   - Should find: "Molicel INR18650 P30B 3000mAh 35A"

2. **Add to Cart:**
   - Quantity: **4 cells** (for 2S2P configuration)
   - Verify specifications:
     - ✅ Capacity: 3000mAh
     - ✅ Continuous discharge: 35A
     - ✅ Chemistry: Li-ion 18650

3. **Shipping:**
   - Destination: Italy
   - Select express if available (worth €3-5 extra)
   - Expected delivery: 3-5 days (18-20 Jan)

4. **Checkout:**
   - Enter shipping address
   - Payment method
   - **IMPORTANT:** Save order confirmation

5. **Documentation:**
   - Update tracker: "Batteries ordered 15/01, ETA 18-20/01"

**Cost:** €14-16
**Arrival:** 18-20 Jan (3-5 days)

**Recommendation:**
- Try Option A tomorrow morning (same-day acquisition)
- If no local stock, already have Option B order placed
- Don't wait beyond tomorrow - order online if local fails

---

## TASK 3: EMAIL ECKSTEIN FOR STS3215 QUOTE (OPTIONAL - 15 min)

**Why:** Long lead time process (quote → approval → order → 7-10 day shipping). Starting now = servos arrive sooner.

### Email Template (Copy-Paste-Send):

```
To: info@eckstein-shop.de
Subject: Quotation Request - 16× Feetech STS3215 Smart Servos

Guten Tag,

I am building a quadruped robot (OpenDuck Mini V3) and need the following components:

SERVOS:
- Product: Feetech STS3215 Smart Servo
- Quantity: 16 units
- Specifications: 20kg·cm torque @ 7.4V, UART/TTL bus control

CONTROLLER (if available):
- Product: FE-URT-1 UART controller
- Quantity: 1 unit
- Note: Already ordered separately, but can cancel if you have it

QUESTIONS:
1. What is the unit price for 16× STS3215 servos?
2. What is the total cost including shipping to Italy?
3. What is the current lead time / delivery estimate?
4. Do you have these servos in stock currently?
5. Can you provide the FE-URT-1 controller as well?

SHIPPING ADDRESS:
[Your Full Name]
[Street Address]
[Postal Code] [City]
Italy

ADDITIONAL:
- If you have servo extension cables compatible with STS3215, please include in quote
- Payment method: Bank transfer or PayPal (whichever you prefer)

Please send quotation with total price in EUR and expected delivery time.

Thank you for your assistance.

Best regards,
[Your Name]
[Your Email]
[Your Phone - Optional]
```

**What to Fill In:**
- [Your Full Name]
- [Street Address]
- [Postal Code] [City]
- [Your Name] (signature)
- [Your Email]
- [Your Phone] (optional, helps for customs)

**Send To:** info@eckstein-shop.de

**Expected Response:** 1-2 business days (quote with pricing)

**Expected Quote:** ~€400-450 for 16 servos + shipping

**Timeline:**
- Quote: 1-2 days
- Order: Immediate after quote approval
- Shipping: 7-10 days after order
- **Total:** 10-14 days from tonight to servo arrival

**Success Check:**
- [ ] Email sent
- [ ] Confirmation email saved
- [ ] Calendar reminder: Check inbox 17-18 Jan for quote

---

## EXECUTION CHECKLIST

### Tonight (Before 01:30):

**MUST DO:**
- [ ] FE-URT-1 ordered on AliExpress (~€50, 20 min)
- [ ] Tracking number saved

**SHOULD DO:**
- [ ] Vape shop list prepared for tomorrow (5 min)
- [ ] Eckstein email sent (15 min)

**OPTIONAL (if can't sleep):**
- [ ] Batteries ordered online as backup (15 min)

### Tomorrow Morning (09:00):

- [ ] Call 5 vape shops for Molicel P30B
- [ ] If found: Drive and acquire (€14-16)
- [ ] If not found: Verify online order placed

### Week 01 Status:

**Critical Path Protected:**
- ✅ FE-URT-1 ordered (arriving when STS3215 servos ready)
- ✅ Batteries acquisition plan (local or online)
- ✅ STS3215 quote process started (10-14 day pipeline)

**Blockers Removed:**
- No 25-day gap when servos arrive (FE-URT-1 ready)
- Power testing possible within 1-5 days (batteries acquired)
- Servo order pipeline started (quote → order → ship)

---

## TROUBLESHOOTING

**Problem: AliExpress payment declined**
- Try PayPal instead of credit card
- Check card has international purchases enabled
- Try different browser (clear cookies)

**Problem: FE-URT-1 out of stock on AliExpress**
- Email Eckstein: info@eckstein-shop.de (faster, more expensive)
- Check RobotShop.com (backup source)
- Worst case: Order from Feetech directly (slow but guaranteed)

**Problem: Batteries nowhere to be found**
- Local: Try electronics repair shops (might have 18650s)
- Online: nkon.nl (Netherlands, fast EU shipping)
- Last resort: Amazon.it (more expensive, but 2-day delivery)

---

## TIME BUDGET

- FE-URT-1 order: 20 min
- Battery research: 10 min
- Eckstein email: 15 min
- **Total: 45 min**

**Hard stop: 01:30** (must go to bed for tomorrow's hardware marathon)

---

*Orders Guide Created: 15 January 2026, 23:30*
*Execution Deadline: 01:30*
*Critical: FE-URT-1 MUST be ordered tonight*
