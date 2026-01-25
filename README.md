# slack_audit_bot
Description:
Slack bot for auditing user

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