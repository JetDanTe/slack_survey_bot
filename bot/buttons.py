def answer_btn(message, user_id):
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": message}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "action_id": "open_answer_modal",
                    "text": {"type": "plain_text", "text": "Answer"},
                    "value": user_id,
                    "style": "primary",
                }
            ],
        },
    ]
