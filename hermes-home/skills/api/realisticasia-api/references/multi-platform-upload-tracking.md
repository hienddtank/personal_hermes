# Multi-Platform Upload Tracking (RA + VTF)

Created: 2026-05-14. Both platforms share the same Laravel backend — identical API patterns, endpoints, and pitfalls. Only base URL and credentials differ.

## Tracking Sheet

**File:** `/host/d/mkt/python/hermes/workspace/tours/tour_upload_tracking.xlsx`

### Columns
| Group | Column | Description |
|---|---|---|
| Source | Tour Name | Display name |
| Source | DOCX Source File | Filename of source DOCX |
| RA | RA Tour ID | Platform-assigned integer ID |
| RA | RA Admin Link | `https://admin.realisticasia.com/travel/tour/{id}` |
| RA | RA Status | Pending / Done / Failed |
| RA | RA Upload Date | ISO date of upload |
| RA | RA Notes | Freeform notes |
| VTF | VTF Tour ID | Platform-assigned integer ID |
| VTF | VTF Admin Link | `https://vtf-admin/travel/tour/{id}` (TBD) |
| VTF | VTF Status | Pending / Done / Failed |
| VTF | VTF Upload Date | ISO date of upload |
| VTF | VTF Notes | Freeform notes |

### Usage
1. Add a row for each new tour DOCX placed in the tours directory
2. After uploading to a platform, fill in Tour ID, Admin Link, Status = Done, Upload Date
3. If upload fails, set Status = Failed and document error in Notes

## README.md

A `README.md` was created in the same directory with:
- API cheat sheet (auth, endpoints, pivot structure)
- Step-by-step upload workflow
- Known pitfalls (POST-only, no DELETE, full object required)

## VTF Onboarding Checklist

When user provides VTF link and credentials:
1. Update README.md with VTF base URL and admin UI URL
2. Update tracking sheet (no schema change needed — columns already exist)
3. Verify auth endpoint works: `POST {vtf_base}/v1/auth/login`
4. Test GET a tour to confirm response format matches RA
