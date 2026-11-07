#!/usr/bin/env bash
set -euo pipefail
umask 077
export PGPASSWORD="$(cat /run/secrets/owner_password)"
case "${1:-}" in
backup)
    temporary="$(mktemp /backups/.dump-XXXXXX)"
    filename="linkspace-$(date -u +%Y%m%dT%H%M%SZ)-${temporary##*.dump-}.dump"
    test ! -e "/backups/$filename"
    trap 'rm -f "$temporary"' EXIT
    pg_dump -h db -U linkspace_owner -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges --file="$temporary"
    mv -n "$temporary" "/backups/$filename"
    printf '%s\n' "$filename"
    ;;
restore)
    # Restore is intentionally restricted to a separately initialized, empty restore database.
    [[ "$POSTGRES_DB" =~ ^restore_[a-zA-Z0-9_]+$ ]] || { echo 'Use an isolated restore_* database'; exit 1; }
    [[ "${BACKUP_FILE:-}" =~ ^[a-zA-Z0-9_.-]+\.dump$ ]] || { echo 'Set a backup basename'; exit 1; }
    count="$(psql -h db -U linkspace_owner -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
    test "$count" = 0 || { echo 'Restore refused: destination is not empty'; exit 1; }
    pg_restore -h db -U linkspace_owner -d "$POSTGRES_DB" --exit-on-error --single-transaction --no-owner --no-privileges "/backups/$BACKUP_FILE"
    echo restore_completed
    ;;
*) echo 'Choose backup or restore'; exit 1 ;;
esac
