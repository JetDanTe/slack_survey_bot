def answer_modal(user_id):
    return {
        "type": "modal",
        "callback_id": "answer_modal_view",
        "title": {"type": "plain_text", "text": "Answer"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": user_id,
        "blocks": [
            {
                "type": "input",
                "block_id": "answer_block",
                "label": {"type": "plain_text", "text": "Your answer"},
                "element": {"type": "plain_text_input", "action_id": "answer_input"},
            }
        ],
    }
