DC = docker compose
BOT_CONTAINER = slack_survey_bot

PHONY: up down build bash
up:
	${DC} up -d

down:
	${DC} down

build:
	${DC} build

bash:
	${DC} exec -it ${BOT_CONTAINER} bash