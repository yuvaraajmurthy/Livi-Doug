# Crisis lines: human verification sheet

**Before the demo, a person calls or checks every line below, then sets `verified = true` for it.**
Until then the API returns `verified: false` and the frontend shows a small "verify" badge outside production.
No model writes or changes any of this content. Source: `seed/crisis_lines.yaml` → table `crisis_lines`.

How to mark one verified (after the call):
```sql
UPDATE crisis_lines SET verified = true, verified_on = '2026-10-11', verified_by = '<initials>' WHERE name = '<name>';
```

| # | Campus | Line | Contact shown | What to check | Source (checked 2026-10-10) | Verified by / when |
|---|---|---|---|---|---|---|
| 1 | All | 988 Suicide & Crisis Lifeline | Call or text 988 | Call connects; text works | https://988lifeline.org/get-help/ | |
| 2 | All | 988 en español | Call 988 then press 2, or text AYUDA to 988 | Spanish option and the AYUDA keyword | https://988lifeline.org/get-help/what-to-expect/ | |
| 3 | All | Crisis Text Line | Text HOME to 741741 | **Keyword conflict:** sources show HOME (SAMHSA), TALK (Camden Wellness Center page) and HELLO (Rutgers Health page). Confirm the current keyword (any text may work) | https://www.samhsa.gov/resource/dbhis/crisis-text-line | |
| 4 | All | Emergency | Call 911 | n/a | n/a | |
| 5 | New Brunswick | CAPS | 848-932-7884; after hours follow the prompts | After-hours prompt really reaches a counselor | https://health.rutgers.edu/medical-and-counseling-services/counseling-services/crisis-intervention | |
| 6 | Newark | Rutgers–Newark Counseling Center | 973-353-5805 (Mon–Fri 8:30–4:30) | Hours | https://studentaffairs.newark.rutgers.edu/health-wellness/counseling-center/suicide-prevention-resources | |
| 7 | Newark | Uwill crisis line (after hours) | 833-646-1526 | Number answers 24/7 for RU-N students. Older pages list 973-623-2323: confirm it is retired | same as 6 | |
| 8 | Camden | Rutgers–Camden Student Wellness Center | 856-225-6005 | Hours; what happens after hours | https://wellnesscenter.camden.rutgers.edu/ | |
| 9 | Camden | Uwill crisis line (after hours) | 833-646-1526 | Number answers 24/7 for Camden students | https://wellnesscenter.camden.rutgers.edu/ (resource guide) | |
| 10 | All | NJ Hopeline | 855-654-6735 | 24/7 | https://www.njhopeline.com/ | |

Also listed by the Camden Wellness Center (not in the card, available if wanted): Camden County Crisis Screening 1-856-428-4357; after-hours nurse line 1-800-424-5090; Rutgers–Camden police 856-225-6111.
