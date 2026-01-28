#!/bin/bash
# FastNetMon args:
#  $1 IP
#  $2 direction
#  $3 pps
#  $4 action (ban/unban)

set -u

IP="$1"
DIRECTION="$2"
PPS="$3"
ACTION="$4"

logger -t fastnetmon-notify "CALLED: $0 ip=$IP dir=$DIRECTION pps=$PPS action=$ACTION args=$*"

# =========================
# USER-CONFIGURABLE OPTIONS
# =========================

EMAIL_NOTIFY="me@rlc.cloud"

SRX_HOST=""
SRX_USER=""
SRX_KEY=""

PY="/usr/bin/env python3"
SCRIPT="/usr/local/bin/srx_netconf_blackhole.py"

NETCONF_TIMEOUT=120

# ---- Commit confirmed toggle (BAN only) ----
# true  = auto-expiring bans (Pattern A)
# false = permanent until explicit unban
USE_COMMIT_CONFIRMED=true
CONFIRM_TIMEOUT=600   # used only when enabled for BAN

LOG_FILE="/var/log/fastnetmon-srx-netconf.log"
touch "$LOG_FILE" 2>/dev/null || true


BAN_COMMIT_FLAGS=""
if [[ "$USE_COMMIT_CONFIRMED" == "true" ]]; then
  BAN_COMMIT_FLAGS="--commit-confirmed --confirm-timeout $CONFIRM_TIMEOUT"
else
  BAN_COMMIT_FLAGS="--no-commit-confirmed"
fi

UNBAN_COMMIT_FLAGS="--no-commit-confirmed"

case "$ACTION" in
  ban)
    DETAILS="$(cat)"

    if command -v mail >/dev/null 2>&1; then
      printf "%s\n" "$DETAILS" | mail \
        -s "FastNetMon: IP $IP blocked ($DIRECTION) ${PPS}pps" \
        "$EMAIL_NOTIFY" >>"$LOG_FILE" 2>&1 || \
        logger -t fastnetmon-notify "WARN: mail failed for ip=$IP"
    fi

    $PY $SCRIPT ban \
      --host "$SRX_HOST" --user "$SRX_USER" --ssh-key "$SRX_KEY" \
      --ip "$IP" --timeout "$NETCONF_TIMEOUT" \
      $BAN_COMMIT_FLAGS \
      >>"$LOG_FILE" 2>&1

    RC=$?
    ;;

  unban)
    $PY $SCRIPT unban \
      --host "$SRX_HOST" --user "$SRX_USER" --ssh-key "$SRX_KEY" \
      --ip "$IP" --timeout "$NETCONF_TIMEOUT" \
      $UNBAN_COMMIT_FLAGS \
      >>"$LOG_FILE" 2>&1

    RC=$?
    ;;

  *)
    logger -t fastnetmon-notify "Unknown action='$ACTION' (args=$*)"
    RC=0
    ;;
esac

logger -t fastnetmon-notify "Python exit code=$RC ip=$IP action=$ACTION"
exit $RC