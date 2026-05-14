# B2B Email Reply Protocol — Session Blueprint

Built May 4, 2026. This is a template structure for B2B CRM/BD tracking protocols.

## Document Structure

```
Title: [Protocol Name]
├── Overview (clarify scope: inbound-only vs full-cycle)
├── Core Requirements (3-5 bullet rules)
├── Workflow (scenario-based sections)
│   ├── First Reply from Partner (they reach out first)
│   ├── Follow-Up (you reach out again, organic reason)
│   └── Meeting Booked / Next Step Taken
├── Column Definitions (field-by-field)
├── Status Quick Reference (table with all CRM statuses)
└── Templates (TBD) — link to Google Doc or other source
```

## Key Design Decisions from This Session

### Contact Date Format: `Q[1-4] YY`
- Use space, not slash: `Q2 26`, NOT `Q2/26`
- Examples: Q1 26, Q2 26, Q3 26, Q4 26

### Newsletter Field: 3-State Dropdown
| State | Who Sets It | Meaning |
|-------|------------|---------|
| New | BD person (you) | Agency just replied; other departments will handle |
| Added | Marketing/Newsletter dept (auto) | On the newsletter list |
| Unsubscribed | Marketing/Newsletter dept (auto) | Opted out or requested removal |

### BD Statuses: Use CRM Values Exactly
From the CRM screenshot: New, Contacted, Communicated, Relationship established, Partner - active, Partner - no activity, Already Have Partner, Inactive, Closed - Not Interested, Not potencial.

### Scope Clarification
If the user only handles inbound responses to outbound campaigns (not initial outreach), remove "First Contact" section entirely. Overview should state: *"You only manage inbound replies to outbound campaigns sent by third-party software."*

## Python Implementation Notes
- Use `\\u2022` for manual bullet characters when doc style doesn't have 'List Bullet'
- Add table rows dynamically with `deepcopy(table._tbl[-1])` before filling
- Write to `/tmp/` first, then `shutil.copy()` to protected paths
- Clear paragraph runs before reusing paragraph element: `for run in p.runs: run.text = ''`
