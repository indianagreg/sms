# SMS Follow-Up Digest

Daily email summary of SMS/iMessage conversations that may need a reply or follow-up.

This project runs locally on your Mac and reads the macOS Messages database at:

```text
~/Library/Messages/chat.db
```

When enabled, it also reads your local Contacts database so phone numbers in the digest can be shown as contact names.

## First-Time Setup

1. Copy the example config:

   ```sh
   cp config.example.json config.json
   ```

2. Edit `config.json` with your email settings.

3. Create `.env` with secrets:

   ```sh
   SMS_FOLLOWUP_SMTP_PASSWORD="your gmail app password"
   OPENAI_API_KEY="your openai api key"
   ```

4. Test Gmail delivery:

   ```sh
   python3 -m sms_followup --config config.json --test-email
   ```

5. Give your terminal or Python runtime Full Disk Access:

   System Settings -> Privacy & Security -> Full Disk Access

   This is needed for Messages and may also be needed for Contacts name matching.

6. Run a dry run:

   ```sh
   python3 -m sms_followup --config config.json --dry-run
   ```

7. Send a real digest:

   ```sh
   python3 -m sms_followup --config config.json
   ```

## Optional LLM Analysis

The built-in rule-based detector works without dependencies. For better judgment, set:

```sh
export OPENAI_API_KEY="..."
```

Then set `"use_openai": true` in `config.json`.

## Daily Scheduling

After `config.json` works, install the LaunchAgent:

```sh
./scripts/install_launch_agent.sh
```

The included template runs every day at 7:30 AM local time.

Logs go to:

```text
~/Library/Logs/sms-followup.out.log
~/Library/Logs/sms-followup.err.log
```
