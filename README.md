# slack_audit_bot
Description:
Slack bot for auditing user

TBD:
1. Add .json config file where will be stored some static data. The main goal remove hardcoded strings.
2. Add possibility to get report from any audit.
3. Update all user info, to only is_deleted state
4. Create docker and docker compose files for auto setup from scratch.
5. Add logging to external file.
6. Add tests

Get slack tokens:
1. https://api.slack.com/apps/YOUR_BOT_ID/oauth?
2. Copy Bot User OAuth Token
3. Set var SLACK_BOT_TOKEN with copied token
4. https://api.slack.com/apps/YOUR_BOT_ID/general?
5. Create or copy token at App-Level Tokens
6. Set var SLACK_APP_TOKEN with copied token

Automate setup:
1. Config file in json format with all key data.
    - Required: first admin user, format provided, without this data you lost ability to use admin command.
    - Users table must be created before admin user added.
    - PUT slack variables inside json before start.
    - Add ability to connect to custom DB from scratch, from json.