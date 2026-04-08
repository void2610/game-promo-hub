# game-promo-hub

Discord bot for managing indie game promotion drafts, scheduling approved posts, and analyzing X/Twitter performance with SQLite and Claude Code CLI.

## Setup

1. Copy `.env.example` to `.env` and fill the required credentials.
2. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
3. Confirm Claude CLI works:
   ```bash
   echo "Translate テスト to English. Respond with English only." | claude --print
   ```
4. Start the bot:
   ```bash
   python3 bot.py
   ```

## Main Commands

- `/game_add`
- `/game_list`
- `/progress_add`
- `/appeal_add`
- `/asset_add`
- `/promo_draft`
- `/analytics_fetch`
- `/analytics_report`
- `/analytics_top`
- `/schedule_slot_add`
- `/schedule_slot_list`
- `/schedule_slot_remove`
- `/schedule_queue_list`
- `/schedule_queue_cancel`

