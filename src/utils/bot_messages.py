# Central place to configure all the bot's static messages — where its
# "personality" shows. Keep user-facing copy here, not inline in commands.
# MIRROR: jobs/deferred_worker/worker_messages.py — keep in sync (GENERAL_ERROR)  # [feature:deferred_worker]

#############################
# Error Messages           #
#############################
GENERAL_ERROR = "Something went wrong! Please try again in a moment."
REQUIRE_MANAGE_SERVER = "Sorry! Only users with the 'Manage Server' permission can do that."
# [feature:dynamodb]

#############################
# Note Messages (example)  #
#############################
NOTE_NOT_FOUND = "No note found with that name. Save one with `/note name content`."
# [/feature:dynamodb]
