# Slack Audit & Survey Bot

A powerful, asynchronous Slack bot built with Python, Slack Bolt, and SQLAlchemy. This bot is designed to manage users, conduct targeted surveys, and automate reminders through dynamic user lists and interactive Slack UI components (Modals and Blocks).

## 🚀 Features

- **Survey Management**: Create, start, stop, and monitor surveys directly within Slack using interactive modals (`/survey_create` etc).
- **Targeted User Lists**: Group users into custom lists and use them to broadcast surveys to specific audiences. Include or exclude specific users dynamically.
- **Smart Reminders**: Automated background reminders for unanswered surveys, along with a "Remind Now" manual trigger.
- **Admin Access Control**: Secure actions with an admin tier. The first admin is configured easily via environment variables.
- **Data Export**: Built-in support (via `pandas` and `openpyxl`) for handling and exporting survey responses.
- **Socket Mode Integration**: Connects securely to Slack using Socket Mode (no public endpoint required).
- **Modern Async Stack**: Leverages `asyncio`, `asyncpg`, and `SQLAlchemy 2.0` for high performance. 

---

## 🛠️ Technology Stack

- **Python 3.12+**
- **Slack Bolt** for app framework and Socket Mode.
- **SQLAlchemy (Async)** & **asyncpg** for ORM and database interactions.
- **Alembic** for automated database migrations.
- **PostgreSQL** as the primary database.
- **Poetry** for dependency management.
- **Docker & Docker Compose** for streamlined deployment.

---

## ⚙️ Setup & Installation

### 1. Create a Slack App
1. Go to [Slack API Apps](https://api.slack.com/apps) and create a new app.
2. In **OAuth & Permissions**, add necessary bot token scopes (e.g., `chat:write`, `users:read`, `slash_commands`).
3. Install the app to your workspace and copy the **Bot User OAuth Token** (`xoxb-...`).
4. Go to **Basic Information > App-Level Tokens** and create a token with `connections:write` scope (`xapp-...`).
5. Enable **Socket Mode** in the sidebar.

### 2. Environment Variables
Clone the repository and set up your environment variables:

```bash
cp .env_example .env
```

Edit the `.env` file to include your Slack credentials, initial Admin ID/Name (required for admin commands), and PostgreSQL connection details:

```env
# Slack
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_ADMIN_ID=U12345678  # Get this from your Slack Profile
SLACK_ADMIN_NAME=AdminName

# Postgres
POSTGRES_DB=survey_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### 3. Running with Docker (Recommended)
The project includes a `docker-compose.yaml` and a `Makefile` for easy deployment. The Docker setup will automatically run database migrations before starting the bot.

To start the bot in the background:
```bash
make up
# Or: docker compose up -d
```

To view logs or rebuild:
```bash
docker compose logs -f slack_survey_bot
make build
```

To stop the bot:
```bash
make down
```

### 4. Running Locally (Development)
If you prefer running without Docker:
1. Ensure a PostgreSQL instance is running.
2. Install dependencies using Poetry:
    ```bash
    poetry install
    ```
3. Run Alembic migrations:
    ```bash
    poetry run alembic upgrade head
    ```
4. Start the bot:
    ```bash
    poetry run python bot/main.py
    ```

---

## 📖 Usage

Once the bot is running and added to your Slack workspace:
1. The **Admin** configured in `.env` will have full access.
2. Users can interact with the bot using Slack commands (e.g., creating a survey or managing lists).
3. The bot utilizes Slack UI Blocks for dynamic management:
   - **User Lists Manager**: Create, view, and update dynamic user lists.
   - **Survey Control Manager**: Start surveys, monitor completion rates, view unanswered users, and trigger instant reminders.

---

## 🏗️ Project Structure

- `bot/`: The core bot application.
  - `main.py` / `slack_bot.py`: App initialization and Socket Mode connection.
  - `handlers/`: Slack event handlers (Surveys, User Lists, Common actions).
  - `services/`: Business logic (Reminders, Modals, Admin initialization).
  - `pyproject.toml`: Poetry configuration.
- `shared/`: Shared services, database CRUD bindings, and settings.
- `migrations/`: Alembic migration scripts.
- `docker-compose.yaml`: Infrastructure definition.