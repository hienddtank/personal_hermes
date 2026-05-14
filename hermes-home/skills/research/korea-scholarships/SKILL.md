---
name: korea-scholarships
description: Search, compare, and apply for scholarships at Korean universities for international students — covering full-coverage programs, government schemes (KGSP/GKS), university-internal packages, and foundation fellowships. Includes a reference database of major STEM-focused universities.
version: 1.0.0
category: research
---

# Korea Scholarships Research

## Quick Rules
- **Verify dates:** Korean scholarship deadlines shift yearly. Always confirm on the official `.ac.kr` or `.go.kr` domain before telling the user a deadline.
- **Internal ≠ government:** "Internal" means university-funded (TA/RA, dean's list, automatic admission scholarships). External means KGSP/GKS (government) or private foundation (POSCO, etc.).
- **Automatic consideration matters:** Many top Korean universities auto-consider all admitted international students for funding — no separate application. Highlight these first.
- **Nationality restrictions vary:** Some scholarships are Asia-only (POSCO Asia Fellowship), some are SE Asia specific (SNU GSFS), some accept all nationalities (GIST, UNIST).

## Target User Profiles

### Vietnamese applicant → eligible for:
- **All nationality-open programs** (GIST, KAIST, POSTECH, UNIST, DGIST)
- **Asia-only programs** (POSCO Asia Fellowship)
- **SE Asia programs** (SNU GSFS — Vietnam is in the eligible region list)

### Materials Science / Engineering focus
For students targeting materials science, prioritize universities with an explicit MSE department:
- **GIST** — Materials Science and Engineering department exists
- **KAIST** — Department of Materials Science and Engineering
- **POSTECH** — Department of Materials Science and Engineering
- **SNU** — Department of Materials Science and Engineering
- **Yonsei** — Department of Materials Science and Engineering
- **Hanyang** — Department of Materials Science and Engineering
- **UNIST** — Advanced Materials Science (department-level program)
- **DGIST** — Energy Science & Engineering (materials-adjacent)
- **SKKU** — School of Advanced Materials Science and Engineering
- **Pusan National** — Department of Materials Science and Engineering

### Korean national → eligible for:
- **대학원 대통령과학장학금** (Presidential Science Scholarship for Graduate Students)
- **한국장학재단 국가장학금** (National Scholarship Types I & II)
- All university-internal scholarships

## Top Tier STEM Universities (Materials Science / Engineering)

### GIST (Gwangju Institute of Science & Technology)
- Materials Science and Engineering is a graduate department
- Auto-funded on admission: full tuition + KRW 140K/mo (MS) or 295K/mo (PhD)
- **No application fee.** Deadline ~April 14 (Fall)
- Portal opens ~March 14 each year

### KAIST
- 94% of international students receive funding
- Base scholarship: full tuition + KRW 350K–400K/mo
- KGPS (Presidential): full tuition + KRW 1M/mo for 4 semesters. Highly competitive
- Apply via [ApplyWeb](https://admission.kaist.ac.kr/intl-graduate/) — select "KAIST Scholarship" checkbox

### POSTECH
- Full tuition for ALL admitted international grad students
- TA/RA: KRW 966K/mo (MS) or 1,316K/mo (PhD). Advisor may add more
- POSCO Global Scholarship (Vietnam eligible): full tuition + KRW 1M/mo + settlement fee + NHIS

### UNIST
- All grad students admitted as government or UNIST scholarship students
- Min KRW 800K/mo (MS) or 1.1M/mo (PhD). Lab participation increases total
- Automatic on admission, no separate application

### DGIST
- Government scholarship: full tuition + min KRW 9.6M/yr (MS), 14M/yr (PhD)
- DGIST-funded scholarship: additional stipend = tuition amount
- On-campus housing at Biseul Village

## Foundation / External Fellowships

### POSCO Asia Fellowship (POSCO Global Scholarship in Korea)
- Asian citizens only. Vietnam eligible
- Full tuition + KRW 1M/mo + settlement KRW 1M + NHIS
- Apply through one of 9 eligible universities: SNU, KAIST, POSTECH, Yonsei, SKKU, Korea University, Hanyang, Kyung Hee, Ewha Womans
- Max 3 university choices. Deadline ~May 31
- Contact: asiafellowship@postf.org

### POSCO TJ Park Global Scholarship (separate from Asia Fellowship)
- Designated countries list changes yearly — Vietnam often included
- Full tuition + KRW 1M/mo for MS/PhD + settlement fee

## Regional / Government Track Programs

### KGSP/GKS (University Recommendation Track)
- Full tuition (~KRW 5M/yr) + ~KRW 900K–1M/mo + airfare + language year
- Apply through individual university international office or Korean Embassy
- Embassy track opens ~February; university track varies (Mar–May)

### SNU GSFS — Graduate Scholarship for Excellent Foreign Students
- East, Southeast, and Central Asia ONLY. Vietnam eligible.
- 100% tuition + KRW 500K–900K/mo
- No separate form — integrated into SNU grad admissions

### K-GKS (Gyeongsangbuk-do Regional Track)
- Requires 3-year residence commitment in the province after graduation
- Same benefits as KGSP + job support program post-graduation
- Apply through POSTECH or partner university

## Application Strategy for Full Coverage

**Priority order:**
1. University internal scholarships with automatic consideration (GIST, UNIST, DGIST, KAIST base) — apply first since no separate app needed
2. Foundation fellowships that stack (POSCO Asia Fellowship can be applied alongside any of the above)
3. KGSP/GKS as backup or if the above don't work out

**Key timing:** Most Fall intake deadlines cluster March–April. Prepare documents (transcripts, letters, English scores) 1–2 months before.

## Presenting Data to Users
- When users ask for scholarship comparison data, **lead with a clean CSV** — not prose descriptions. The user's "try again" feedback signals that long verbose tables are hard to parse.
- **CSV format guidelines:** Use standardized, terse column headers (University, Scholarship, Program, Coverage, Tuition, Stipend, Monthly Allowance, Language Req, Nationality, App Fee, Deadline, URL, Note). Keep cell content concise — avoid sentences in individual cells. Separate internal university scholarships from external/foundation ones clearly.
- **Priority ordering:** Sort by coverage level (100% first), then by ease of application (automatic/checkbox > separate application).
- **Always check this skill exists** before starting a Korea scholarship research session. Load it via `skill_view(name='korea-scholarships')` first.

## Pitfalls
- **GKS vs university internal are separate tracks:** Some universities let you combine one with a foundation scholarship; others (like Hanyang's HIEA) explicitly exclude GKS recipients. Check each program's combination rules.
- **English proficiency scores must be from the right test format:** TOEFL Home Edition and IELTS Indicator are NOT accepted by Korea University. Verify which test formats each university accepts.
- **SKKU STEM requires contacting a professor first:** This is a MANDATORY requirement — not contacting an advisor before applying will result in automatic disqualification for their STEM scholarship track.
- **Yonsei's HIEA excludes GKS recipients:** If you're receiving any external scholarship, you cannot apply for the Hanyang International Excellence Award (HIEA).
- **Deadlines shift:** Always confirm current deadlines on official .ac.kr or .go.kr domains — third-party sites may have outdated dates.

## Related Files
- `references/korea-scholarships-reference.md` — detailed scholarship database with coverage amounts, eligibility, URLs, and deadline tracking
