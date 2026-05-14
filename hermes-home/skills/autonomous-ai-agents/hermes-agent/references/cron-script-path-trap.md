# Cron Script Path Trap

## The Bug
In Hermes Agent cron job context, `~` resolves to `/hermes-home/`, NOT `/root/`. Interactive shell resolves `~` to `/root/`.

This means scripts written via `write_file` from an interactive session land in `/root/.hermes/scripts/` but cron looks at `/hermes-home/scripts/`.

## Symptoms
- Cron job reports: "Script not found" or path error
- Script exists when you check interactively: `ls ~/.hermes/scripts/`
- Script does NOT exist at `/hermes-home/scripts/`

## Debug Steps
```bash
# 1. Check cron's HOME
echo $HOME  # Interactive: /root, Cron context: /hermes-home

# 2. Where the script actually is
ls -la /root/.hermes/scripts/heartbeat_check.sh    # Interactive view
ls -la /hermes-home/scripts/heartbeat_check.sh     # Cron view — often missing!

# 3. Verify cronjob's expected path
cronjob list  # Shows which scripts are referenced
```

## Fix
Copy or symlink to the cron-visible location:
```bash
cp ~/.hermes/scripts/my_script.sh /hermes-home/scripts/
chmod +x /hermes-home/scripts/my_script.sh
```

Or always use `/hermes-home/scripts/` when writing cron scripts.

## Affected Scripts (This Session — May 1, 2026)
- `heartbeat_check.sh` — missing at `/hermes-home/scripts/`, was at `/root/.hermes/scripts/`
- Potentially `check-forwarders.sh` — same pattern, may have the same issue

## Prevention
Always use absolute paths (`/hermes-home/scripts/`) when writing files intended for cron jobs. Never rely on `~` expansion in cron contexts.
