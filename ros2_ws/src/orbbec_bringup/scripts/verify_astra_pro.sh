#!/usr/bin/env bash
# Phase 1 acceptance check for the Astra Pro.
#
# Run this in a second terminal WHILE orbbec_with_mount.launch.py is running.
# Every check prints PASS or FAIL; Phase 1 is done when all of them pass and
# the numbers hold steady for 60 s.
#
#   source install/setup.bash
#   bash ros2_ws/src/orbbec_bringup/scripts/verify_astra_pro.sh
set -uo pipefail

CAMERA="${CAMERA_NAME:-camera}"
BASE_FRAME="${BASE_FRAME:-base_link}"
FAILURES=0

pass() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

echo "== 1. USB enumeration =="
if lsusb -d 2bc5: | grep -q .; then
  lsusb -d 2bc5: | sed 's/^/        /'
  DEPTH_OK=$(lsusb -d 2bc5:0403 | grep -c . || true)
  [ "${DEPTH_OK}" -ge 1 ] && pass "depth sensor (2bc5:0403) present" \
                          || fail "depth sensor (2bc5:0403) missing"
  UVC_OK=$(lsusb -d 2bc5: | grep -cE ':05[0-9a-f]{2}' || true)
  [ "${UVC_OK}" -ge 1 ] && pass "RGB UVC device present" \
                        || fail "RGB UVC device missing - check the VM USB passthrough"
else
  fail "no 2bc5 device on the USB bus at all"
fi

echo "== 2. Topics present =="
TOPICS="$(ros2 topic list 2>/dev/null)"
for t in "/${CAMERA}/color/image_raw" "/${CAMERA}/color/camera_info" \
         "/${CAMERA}/depth/image_raw" "/${CAMERA}/depth/camera_info" \
         "/${CAMERA}/depth/points"; do
  echo "${TOPICS}" | grep -qx "${t}" && pass "${t}" || fail "${t} not advertised"
done

echo "== 3. Topics actually publishing (5 s window each) =="
check_hz() {
  local topic="$1" min="$2"
  local hz
  hz=$(timeout 8 ros2 topic hz "${topic}" --window 20 2>/dev/null \
       | grep -oP 'average rate: \K[0-9.]+' | tail -1)
  if [ -z "${hz}" ]; then
    fail "${topic}: no messages"
  elif awk "BEGIN{exit !(${hz} >= ${min})}"; then
    pass "${topic}: ${hz} Hz"
  else
    fail "${topic}: only ${hz} Hz (expected >= ${min})"
  fi
}
check_hz "/${CAMERA}/color/image_raw" "${MIN_COLOR_HZ:-10}"
check_hz "/${CAMERA}/depth/image_raw" 10
check_hz "/${CAMERA}/depth/points" 5

echo "== 4. CameraInfo is populated =="
INFO="$(timeout 8 ros2 topic echo --once "/${CAMERA}/depth/camera_info" 2>/dev/null)"
if echo "${INFO}" | grep -qE '^\s*-\s*[1-9]'; then
  pass "depth/camera_info has a non-zero K matrix"
else
  fail "depth/camera_info looks empty - the driver did not read intrinsics"
fi
CINFO="$(timeout 8 ros2 topic echo --once "/${CAMERA}/color/camera_info" 2>/dev/null)"
if echo "${CINFO}" | grep -q 'plumb_bob'; then
  pass "color/camera_info published (factory values until you calibrate)"
else
  fail "color/camera_info missing or malformed"
fi

echo "== 5. TF chain ${BASE_FRAME} -> ${CAMERA}_depth_optical_frame =="
if timeout 8 ros2 run tf2_ros tf2_echo "${BASE_FRAME}" "${CAMERA}_depth_optical_frame" \
     2>/dev/null | grep -q 'Translation'; then
  pass "TF resolves end to end"
else
  fail "TF does not resolve - is camera_mount.launch.py running, and is x/y/z set?"
fi

echo
if [ "${FAILURES}" -eq 0 ]; then
  echo "Phase 1: ALL CHECKS PASSED"
else
  echo "Phase 1: ${FAILURES} check(s) failed - see the troubleshooting table in README.md"
fi
exit "${FAILURES}"
