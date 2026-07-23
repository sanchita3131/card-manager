# Error Analysis — Card2 Extraction Failure

## Card Details
A business card for **Rajiv Terwadkar** (Founder/Director at Neural Stream).

## OCR Output
```
[1.00] Founder, Director
[0.97] RAJIV TERWADKAR
[0.96] +91 9370707477
[0.99] Shri GanRaj, Plot No. 1O, Lane 4,
[1.00] Tuljainagar, Sangli, Maharashtra,
[0.96] India - 416416
[1.00] rajiv@neural-stream.com
[1.00] www.neural-stream.com
```

## What Went Wrong

The scoring system made two mistakes:

### ❌ Mistake 1: Address assigned as Name
`Tuljainagar, Sangli, Maharashtra` was assigned to the **name** field because:
- It starts with a capitalized word
- It has multiple words (2-5 = name score bonus)
- It has no digits (name score bonus)
- No position keywords matched (name score bonus)
- The scoring system had **zero awareness of address patterns**

### ❌ Mistake 2: Person name assigned as Company
`RAJIV TERWADKAR` was assigned to the **company** field because:
- ALL-CAPS text longer than 3 chars → +30 company score
- No company suffix needed → it looked like a brand name
- The name score got a -20 penalty for being all-caps + longer than 6 chars
- Net result: company score (35) > name score (might be lower)

### ❌ Cascade
- Company took "RAJIV TERWADKAR" first
- Name took the next best option: the address line
- Position was correctly identified ("Founder, Director")
- Phone and email (regex) were fine

## What Was Fixed

### Fix 1: Address Detection (`_is_address_line()`)
Added a new helper that detects address patterns:
- **Comma test**: 2+ commas in a line → likely an address (e.g. `Tuljainagar, Sangli, Maharashtra,`)
- **Keyword test**: Indian address words like "nagar", "colony", "sangli", "maharashtra", "lane", "road", "plot"
- **Postal code test**: 5-6 digit numbers (pincodes/zip codes)
- Address lines are marked as "address" and excluded from name/company/position scoring

### Fix 2: ALL-CAPS Name vs Company Disambiguation
- **Before**: ALL-CAPS text always got +30 company score and -20 name penalty
- **After**: 2-3 word ALL-CAPS text gets only +5 company score (was +30) and +15 name score (was -20)
- This makes "RAJIV TERWADKAR" score higher as a name than as a company

### Fix 3: Assignment Priority Changed
- **Before**: position → company → name (company had first pick of remaining lines)
- **After**: name → position → company (name gets first pick)
- Reason: on cards without an explicit company name (freelancers/solopreneurs), the person's name is the most important field to get right

### Fix 4: Round 4 Conflict Resolution
- Round 4 now respects the `taken` set — if a line was already assigned to one entity, it won't be assigned to another
- Prevents the same text from appearing in both name AND company

### Fix 5: Email Domain as Company Fallback
- If company is still null after all rounds → extract from email domain
- `rajiv@neural-stream.com` → `Neural Stream`
- Also fires if company == name (they're the same text, company is wrong)

## Result
```
Before:                     After:
  company: RAJIV TERWADKAR    company: Neural Stream
  name: Tuljainagar, ...      name: RAJIV TERWADKAR
  position: Founder, Dir.     position: Founder, Dir.
  phone: +91 9370707477       phone: +91 9370707477
  email: rajiv@neural-stream  email: rajiv@neural-stream
```
