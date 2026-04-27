#!/bin/sh
set -eu

cd /Users/greg/sms
exec /usr/bin/python3 -m sms_followup --config /Users/greg/sms/config.json
