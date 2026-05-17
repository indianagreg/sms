# SMS Follow-Up Digest

Daily email summary of SMS/iMessage conversations that may need a reply or follow-up.

This project runs locally on your Mac and reads the macOS Messages database at:

```text
~/Library/Messages/chat.db
```

When enabled, it also reads your local Contacts database so phone numbers in the digest can be shown as contact names.

## First-Time Setup

1. Clone this repository on the Mac that has Messages synced.

2. Optional: install the command locally:

   ```sh
   python3 -m pip install .
   ```

3. Create the app config directory:

   ```sh
   mkdir -p ~/.sms-followup
   cp config.example.json ~/.sms-followup/config.json
   ```

4. Edit `~/.sms-followup/config.json` with your email settings.

5. Create `~/.sms-followup/.env` with secrets:

   ```sh
   SMS_FOLLOWUP_SMTP_PASSWORD="your gmail app password"
   OPENROUTER_API_KEY="your openrouter api key"
   ```

   Then lock down the file:

   ```sh
   chmod 600 ~/.sms-followup/.env
   ```

6. Test Gmail delivery:

   ```sh
   python3 -m sms_followup --test-email
   ```

   If installed with `pip`, this also works:

   ```sh
   sms-followup --test-email
   ```

7. Give your terminal or Python runtime Full Disk Access:

   System Settings -> Privacy & Security -> Full Disk Access

   This is needed for Messages and may also be needed for Contacts name matching.

8. Run a dry run:

   ```sh
   python3 -m sms_followup --dry-run
   ```

9. Send a real digest:

   ```sh
   python3 -m sms_followup
   ```

## Optional AI Analysis

The built-in rule-based detector works without dependencies. For better judgment across every conversation in the lookback window, set:

```sh
export OPENROUTER_API_KEY="..."
```

Then set these in `~/.sms-followup/config.json`:

```json
"use_ai": true,
"openrouter_model": "openai/gpt-4.1-mini"
```

You can change `openrouter_model` to any model ID supported by OpenRouter.

## Daily Scheduling

After `~/.sms-followup/config.json` works, install the LaunchAgent:

```sh
./scripts/install_launch_agent.sh
```

The included template runs every day at 7:30 AM local time.

The installer creates these files if they do not already exist:

```text
~/.sms-followup/config.json
~/.sms-followup/.env
~/Library/LaunchAgents/com.sms-followup.daily.plist
```

Logs go to:

```text
~/Library/Logs/sms-followup.out.log
~/Library/Logs/sms-followup.err.log
```
